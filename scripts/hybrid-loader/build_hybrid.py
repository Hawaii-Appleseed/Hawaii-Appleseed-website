"""PARKED EXPERIMENT - not wired into squarespace.py. See README.md in this folder.

Usage: python3 build_hybrid.py <payload.html> <pages-url-of-that-payload> <out.html>
Example:
  python3 build_hybrid.py ../../squarespace-ready/food-security.html \
    https://hawaii-appleseed.github.io/Hawaii-Appleseed-website/squarespace-ready/food-security.html /tmp/food-hybrid.html
"""
import hashlib, sys
src_file, url, out = sys.argv[1:4]
snap = open(src_file, encoding="utf-8").read()
h = hashlib.sha256(snap.encode("utf-8")).hexdigest()
loader = """
<script>
(function () {
  var root = document.getElementById("ha-live-root");
  if (!root || !window.fetch || !window.crypto || !crypto.subtle) return;
  var src = root.getAttribute("data-src"), have = root.getAttribute("data-sha256");
  fetch(src, { cache: "no-cache" }).then(function (r) {
    if (!r.ok) throw new Error(r.status); return r.text();
  }).then(function (html) {
    return crypto.subtle.digest("SHA-256", new TextEncoder().encode(html)).then(function (buf) {
      var hex = Array.prototype.map.call(new Uint8Array(buf), function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
      if (hex === have) return;
      var doc = new DOMParser().parseFromString(html, "text/html");
      var nodes = Array.prototype.slice.call(doc.head.childNodes).concat(Array.prototype.slice.call(doc.body.childNodes));
      var frag = document.createDocumentFragment();
      nodes.forEach(function (n) {
        if (n.nodeType !== 1) return;
        if (n.tagName === "SCRIPT") {
          var s = document.createElement("script");
          if (n.src) s.src = n.src; else s.textContent = n.textContent;
          frag.appendChild(s);
        } else frag.appendChild(document.importNode(n, true));
      });
      root.replaceChildren(frag);
      root.setAttribute("data-sha256", hex);
      root.setAttribute("data-refreshed", "1");
    });
  }).catch(function () { /* keep the snapshot */ });
})();
</script>
"""
open(out, "w", encoding="utf-8").write(
  '<div id="ha-live-root" data-src="%s" data-sha256="%s">\n%s\n</div>\n%s' % (url, h, snap, loader))
print(len(open(out, encoding="utf-8").read()), h[:12])
