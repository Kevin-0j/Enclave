(function () {
  try {
    var s = JSON.parse(localStorage.getItem("enclave.settings.v1") || "{}");
    var t = s.theme || "dark";
    var dark = t === "dark" || (t === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  } catch (e) {
    document.documentElement.dataset.theme = "dark";
  }
})();
