"""A short independent MQTT authentication test, without publishing or changing config."""
import asyncio
import secrets
import paho.mqtt.client as paho


async def probe(settings):
    loop = asyncio.get_running_loop()
    result = loop.create_future()
    client = paho.Client(paho.CallbackAPIVersion.VERSION2, client_id='hub-probe-'+secrets.token_hex(6))
    client.max_queued_messages_set(1)
    client.connect_timeout = 3
    if settings.username or settings.password:
        client.username_pw_set(settings.username, settings.password)
    if settings.tls:
        client.tls_set()

    def finish(ok, message):
        if not result.done():
            result.set_result({'ok': ok, 'message': message})

    def connected(client_, userdata, flags, reason, properties):
        loop.call_soon_threadsafe(finish, not reason.is_failure,
            "MQTT connection and authentication succeeded." if not reason.is_failure else "The broker rejected the MQTT connection.")

    def failed(client_, userdata):
        loop.call_soon_threadsafe(finish, False, "Could not connect to the MQTT broker.")

    client.on_connect = connected
    client.on_connect_fail = failed
    try:
        client.connect_async(settings.host, settings.port, keepalive=10)
        client.loop_start()
        return await asyncio.wait_for(result, 6)
    except (TimeoutError, OSError, ValueError):
        return {'ok': False, 'message': "No valid MQTT broker response before timeout."}
    finally:
        client.disconnect()
        try:
            await asyncio.wait_for(asyncio.to_thread(client.loop_stop), 4)
        except TimeoutError:
            pass
