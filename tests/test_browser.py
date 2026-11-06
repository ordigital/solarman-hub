"""Optional browser smoke: HUB_TEST_BROWSER=1 pytest -q tests/test_browser.py."""
import asyncio
import os
from pathlib import Path
import pytest
from aiohttp.test_utils import TestServer
from solarman_hub import __version__
from solarman_hub.runtime import Runtime
from solarman_hub.web import create_app
from solarman_hub.auth import password_record, save_password

@pytest.mark.skipif(os.environ.get('HUB_TEST_BROWSER') != '1', reason='Opt-in: requires installed Playwright Chromium')
async def test_browser_onboarding_decode_and_profiles(tmp_path):
    from playwright.async_api import async_playwright, expect
    runtime=Runtime(tmp_path,tcp_host='127.0.0.1',tcp_port=0)
    save_password(tmp_path, password_record('browser test administrator password'))
    server=TestServer(create_app(runtime))
    await server.start_server();await runtime.start()
    writer=None
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True)
            page=await browser.new_page(viewport={'width':1440,'height':1000})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            await page.goto(str(server.make_url('/')))
            await page.evaluate('() => I18n.ready')
            for width,height in ((1366,768),(1280,720),(1920,1080),(390,844)):
                await page.set_viewport_size({'width':width,'height':height})
                for language in ('en','pl','de','fr','cs','sk','lt','uk','ru'):
                    await page.locator('.login-screen [data-language]').select_option(language)
                    geometry=await page.evaluate("""() => ({height:innerHeight,scroll:document.documentElement.scrollHeight,
                        button:document.querySelector('#login-form button').getBoundingClientRect().bottom,
                        language:document.querySelector('.login-screen [data-language]').getBoundingClientRect().bottom})""")
                    assert geometry['scroll']<=geometry['height']+1,(width,height,language,geometry)
                    assert geometry['button']<=height and geometry['language']<=height,(width,height,language,geometry)
            await page.set_viewport_size({'width':1440,'height':1000})
            await page.locator('.login-screen [data-language]').select_option('pl')
            await page.locator('#admin-token').fill('invalid test token')
            await page.locator('#login-form button').click()
            invalid_token=await page.evaluate("I18n.t('Invalid password or administrator token')")
            await expect(page.locator('#login-error')).to_have_text(invalid_token)
            await page.locator('#admin-token').fill('browser test administrator password')
            await page.locator('#login-form button').click()
            await expect(page.locator('#app')).to_be_visible()
            await expect(page.locator('#app-version')).to_have_text('Solarman V5 · v'+__version__)
            await page.locator('[data-view=settings]').click()
            async def mqtt_failure(route):
                await route.fulfill(status=400, json={'ok': False, 'message': 'Could not connect to the MQTT broker.'})
            await page.route('**/api/mqtt/test', mqtt_failure)
            await page.locator('#test-mqtt').click()
            mqtt_error = await page.evaluate("I18n.t('Could not connect to the MQTT broker.')")
            await expect(page.locator('#mqtt-test-result')).to_have_text(mqtt_error)
            await expect(page.locator('#toast')).to_have_text(mqtt_error)
            await page.unroute('**/api/mqtt/test', mqtt_failure)
            await page.locator('[data-config="cloud.enabled"]').uncheck()
            await page.locator('#add-logger').click()
            await page.locator('[data-logger=serial]').fill('1234567890')
            await page.locator('[data-logger=name]').fill('Testowy falownik')
            await page.locator('[data-config="mqtt.username"]').fill('unsaved draft')
            await page.locator('#mqtt-password').fill('unsaved password')
            for code,title in [('en','Configuration'),('de','Konfiguration'),('fr','Configuration'),('cs','Konfigurace'),('sk','Konfigurácia'),('lt','Konfigūracija'),('uk','Налаштування'),('ru','Настройки'),('pl','Konfiguracja')]:
                await page.locator('.topbar [data-language]').select_option(code)
                await expect(page.locator('html')).to_have_attribute('lang',code)
                await expect(page.locator('#page-title')).to_have_text(title)
                # Wrapped HTML help text must follow the selected language too.
                cloud_help=await page.evaluate("I18n.t('When the cloud is unavailable, known frames receive local ACKs. Outage reports stay local; cloud history backfill is not supported.')")
                await expect(page.locator('[data-config=\"cloud.enabled\"]').locator('xpath=ancestor::article').locator('.hint')).to_have_text(cloud_help)
                await expect(page.locator('[data-config="mqtt.username"]')).to_have_value('unsaved draft')
                await expect(page.locator('#mqtt-password')).to_have_value('unsaved password')
                await expect(page.locator('[data-logger=name]')).to_have_value('Testowy falownik')
            await page.locator('[data-config="mqtt.username"]').fill('')
            await page.locator('#mqtt-password').fill('')
            await page.locator('#config-form button[type=submit]').click()
            await expect(page.locator('#toast')).to_contain_text('Zapisano konfigurację')
            await page.locator('#apply-settings').click()
            await expect(page.locator('#toast')).to_contain_text('Zastosowano')
            reader,writer=await asyncio.open_connection('127.0.0.1',runtime.tcp_port)
            writer.write(bytes.fromhex((Path(__file__).parent/'fixtures/sofar-report.hex').read_text()));await writer.drain()
            assert (await asyncio.wait_for(reader.read(256),2))[0]==0xa5
            await page.locator('[data-view=dashboard]').click()
            await expect(page.locator('#measurement-count')).to_have_text('Pola: 48',timeout=10000)
            await page.locator('#measurement-filter').fill('grid_frequency')
            await expect(page.locator('#measurements-body tr')).to_have_count(1)
            await runtime.history.queue.join()
            await page.locator('#measurements-body button').first.click()
            await expect(page.locator('#chart-dialog')).to_be_visible()
            await expect(page.locator('#chart-svg .chart-line')).to_have_count(1)
            delayed,release,finished=asyncio.Event(),asyncio.Event(),asyncio.Event()
            calls=0
            async def delayed_series(route):
                nonlocal calls
                calls+=1;current=calls
                response=await route.fetch();data=await response.json()
                data['name']='old response' if current==1 else 'newest response'
                if current==1:
                    delayed.set();await release.wait()
                await route.fulfill(json=data)
                if current==1:finished.set()
            pattern='**/api/history/*/series?**'
            await page.route(pattern,delayed_series)
            try:
                await page.locator('#chart-range').select_option('604800')
                await asyncio.wait_for(delayed.wait(),3)
                await page.locator('#chart-range').select_option('3600')
                await expect(page.locator('#chart-title')).to_contain_text('newest response')
                release.set();await asyncio.wait_for(finished.wait(),3)
                await expect(page.locator('#chart-title')).to_contain_text('newest response')
            finally:
                release.set();await page.unroute(pattern,delayed_series)
            await page.locator('#chart-close').click()
            await page.locator('#data-mode').select_option('history')
            await expect(page.locator('#history-sample option')).to_have_count(1)
            await page.locator('#history-range').select_option('0')
            await page.locator('#history-from').fill('2026-11-07T12:00')
            await page.locator('#history-to').fill('2026-11-06T12:00')
            await page.locator('#history-load').click()
            invalid=await page.evaluate("I18n.t('Choose a valid time range.')")
            await expect(page.locator('#history-state')).to_have_text(invalid)
            await page.locator('#history-range').select_option('86400')
            await expect(page.locator('#history-state')).not_to_have_text(invalid)
            await expect(page.locator('#measurements-body tr')).to_have_count(1)
            await page.locator('#data-mode').select_option('latest')
            await page.locator('[data-view=devices]').click()
            await expect(page.locator('#device-cards')).to_contain_text('1234567890')
            await page.locator('[data-view=profiles]').click()
            await expect(page.locator('#profile-json')).to_have_attribute('readonly','')
            await page.locator('#clone-profile').click();await page.locator('#save-profile').click()
            await expect(page.locator('#toast')).to_contain_text('Profil zapisany')
            await page.locator('[data-view=help]').click()
            for code in ('en','pl','de','fr','cs','sk','lt','uk','ru'):
                await page.locator('.topbar [data-language]').select_option(code)
                await expect(page.locator('#manual h1')).to_contain_text('Solarman Hub')
                await expect(page.locator('#guide-toc button')).to_have_count(10)
                await page.locator('#guide-toc [data-chapter=esp32]').click()
                await expect(page.locator('#guide-esp32')).to_be_in_viewport()
            await page.locator('[data-go=firmware]').click()
            await expect(page.locator('#view-firmware')).to_be_visible()
            await expect(page.locator('#firmware-instructions')).to_contain_text('esp-flash flash-id')
            async with page.expect_download() as download_info:
                await page.locator('#view-firmware a[href="/api/firmware/factory.bin"]').click()
            assert (await download_info.value).suggested_filename=='factory.bin'
            for code in ('en','pl','de','fr','cs','sk','lt','uk','ru'):
                await page.locator('.topbar [data-language]').select_option(code)
                guide=await (await page.request.get(str(server.make_url('/api/docs?lang='+code)))).json()
                title=next(item['title'] for item in guide['toc'] if item['id']=='esp32')
                await expect(page.locator('#firmware-guide-esp32')).to_have_text(title)
                await expect(page.locator('#firmware-instructions h2')).to_have_count(2)
                await expect(page.locator('#guide-esp32')).to_have_count(1)
                assert await page.locator('#page-title').inner_text()!='ESP32 / Flashing' or code=='en'
            await page.locator('.topbar [data-language]').select_option('pl')
            await page.locator('[data-view=logs]').click()
            await expect(page.locator('#log-level option')).to_have_count(4)
            await expect(page.locator('#logs-body tr').first).to_be_visible()
            await page.locator('[data-view=dashboard]').click()
            await page.locator('#measurement-filter').fill('')
            artifacts=os.environ.get('HUB_TEST_ARTIFACTS')
            if artifacts:
                Path(artifacts).mkdir(parents=True,exist_ok=True)
                await page.screenshot(path=str(Path(artifacts)/'desktop.png'),full_page=True)
            await page.set_viewport_size({'width':390,'height':844})
            assert await page.evaluate("getComputedStyle(document.documentElement).zoom === '1.4'")
            for code in ('en','pl','de','fr','cs','sk','lt','uk','ru'):
                await page.locator('.topbar [data-language]').select_option(code)
                assert await page.evaluate('document.body.getBoundingClientRect().right <= innerWidth + 1'), code
                geometry=await page.evaluate("""() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
                    offenders:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth)
                        .slice(0,12).map(e=>({tag:e.tagName,classes:e.className,text:e.textContent.trim().slice(0,60),right:e.getBoundingClientRect().right}))})""")
                assert geometry['scrollWidth'] <= geometry['width'], (code, geometry)
            await page.locator('[data-view=firmware]').click()
            for code in ('en','pl','de','fr','cs','sk','lt','uk','ru'):
                await page.locator('.topbar [data-language]').select_option(code)
                guide=await (await page.request.get(str(server.make_url('/api/docs?lang='+code)))).json()
                title=next(item['title'] for item in guide['toc'] if item['id']=='esp32')
                await expect(page.locator('#firmware-guide-esp32')).to_have_text(title)
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),code
            await page.reload()
            await expect(page.locator('html')).to_have_attribute('lang','ru')
            await expect(page.locator('#app')).to_be_visible()
            if artifacts:await page.screenshot(path=str(Path(artifacts)/'mobile.png'),full_page=True)
            assert not errors,errors
            await browser.close()
    finally:
        if writer:writer.close();await writer.wait_closed()
        await server.close();await runtime.close()
