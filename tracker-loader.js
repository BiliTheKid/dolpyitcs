/**
 * Dolpyitcs Loader - Embed this tiny snippet on your website
 * ~300 bytes minified
 */
(function(w,d,s,e){
  // Create queue for events before full script loads
  w.dolpyitcs=w.dolpyitcs||{q:[],track:function(){this.q.push(['track',arguments])},identify:function(){this.q.push(['identify',arguments])}};
  // Load full tracker script
  var js=d.createElement(s);js.async=1;
  js.src=e;d.head.appendChild(js);
})(window,document,'script','https://dolpyitcs-cdn.pages.dev/tracker.js');

/**
 * MINIFIED VERSION (paste this on your website):
 *
 * <script>
 * (function(w,d,s,e){w.dolpyitcs=w.dolpyitcs||{q:[],track:function(){this.q.push(['track',arguments])},identify:function(){this.q.push(['identify',arguments])}};var js=d.createElement(s);js.async=1;js.src=e;d.head.appendChild(js)})(window,document,'script','https://dolpyitcs-cdn.pages.dev/tracker.js');
 * </script>
 *
 * UPDATE the URL to your Cloudflare Pages URL after deployment!
 */
