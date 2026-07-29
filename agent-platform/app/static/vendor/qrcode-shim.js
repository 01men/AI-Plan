/* QRCode.toCanvas 兼容垫片：基于 qrcode-generator（vendor/qrcode.min.js，全局函数 qrcode）
   复刻 node-qrcode 浏览器版的 toCanvas 签名，保证 app.js 无需感知底层库差异 */
window.QRCode = {
  toCanvas: function (canvas, text, opts, cb) {
    try {
      var qr = qrcode(0, 'M');
      qr.addData(text);
      qr.make();
      var size = (opts && opts.width) || 220;
      var count = qr.getModuleCount();
      var cell = Math.max(2, Math.floor(size / (count + 2)));
      var margin = cell;
      canvas.width = canvas.height = cell * count + margin * 2;
      var ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#000000';
      for (var r = 0; r < count; r++) {
        for (var c = 0; c < count; c++) {
          if (qr.isDark(r, c)) ctx.fillRect(margin + c * cell, margin + r * cell, cell, cell);
        }
      }
      if (cb) cb(null);
    } catch (e) {
      if (cb) cb(e);
    }
  }
};
