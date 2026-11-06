"use strict";
// English source messages, data-only dictionaries; no translation of user content.
window.I18n = (() => {
  const locales = {
    en: "en-GB",
    pl: "pl-PL",
    de: "de-DE",
    fr: "fr-FR",
    cs: "cs-CZ",
    sk: "sk-SK",
    lt: "lt-LT",
    uk: "uk-UA",
    ru: "ru-RU",
  };
  let language = "pl",
    catalog = {},
    bindings = [],
    aliases = {};
  try {
    const saved = localStorage.getItem("hub-language");
    if (saved in locales) language = saved;
  } catch (_) {
    /* Private browsing can disable storage. */
  }
  function t(message, values = {}) {
    const key = aliases[message] ?? message;
    const text = catalog[language]?.[key] ?? catalog.en?.[key] ?? message;
    return String(text).replace(/\{(\w+)\}/g, (match, key) =>
      Object.hasOwn(values, key) ? String(values[key]) : match,
    );
  }
  function translateDocument() {
    document.documentElement.lang = language;
    for (const binding of bindings) {
      const value = binding.prefix + t(binding.key) + binding.suffix;
      if (binding.attribute)
        binding.node.setAttribute(binding.attribute, value);
      else binding.node.nodeValue = value;
    }
    document
      .querySelectorAll("[data-language]")
      .forEach((select) => (select.value = language));
  }
  function setLanguage(value) {
    if (!(value in locales)) return;
    language = value;
    try {
      localStorage.setItem("hub-language", value);
    } catch (_) {}
    translateDocument();
    window.dispatchEvent(new Event("hub-language-change"));
  }
  const ready = (async () => {
    const response = await fetch("/static/locales.json");
    if (!response.ok) throw Error("Could not load interface translations");
    catalog = await response.json();
    aliases = Object.fromEntries(
      Object.entries(catalog.pl).map(([key, value]) => [value, key]),
    );
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
    );
    while (walker.nextNode()) {
      const node = walker.currentNode,
        key = node.nodeValue.trim().replace(/\s+/g, " ");
      if (
        Object.hasOwn(catalog.en, key) &&
        !node.parentElement.closest("script,style,pre,code,textarea")
      ) {
        const prefix = node.nodeValue.match(/^\s*/)[0];
        const suffix = node.nodeValue.match(/\s*$/)[0];
        bindings.push({
          node,
          key,
          prefix,
          suffix,
        });
      }
    }
    document
      .querySelectorAll("[placeholder],[title],[aria-label]")
      .forEach((node) => {
        for (const attribute of ["placeholder", "title", "aria-label"]) {
          const key = node.getAttribute(attribute);
          if (Object.hasOwn(catalog.en, key))
            bindings.push({ node, key, attribute, prefix: "", suffix: "" });
        }
      });
    document
      .querySelectorAll("[data-language]")
      .forEach((select) =>
        select.addEventListener("change", () => setLanguage(select.value)),
      );
    translateDocument();
  })();
  return {
    t,
    ready,
    setLanguage,
    get language() {
      return language;
    },
    get locale() {
      return locales[language];
    },
  };
})();
