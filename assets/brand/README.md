# Brand assets

原本の PNG / SVG はなく、提供された `olnm-overview.jpg`（1536×1024 JPEG）から切り出しています。JPEG 由来のため、拡大するとブロックノイズが出ます。512px 級のアバターには向きません。再色・マスク・透明化はしていません。角の余りは、切り出し元のカード背景色 (RGB 246, 250, 253) で正方形に揃えています。

- [アイコン](olnm-icon.png): 切り出し箱 `(18, 14, 376, 346)`（右・下は含まない、358×332）。背景で 358×358 にパディング。
- [favicon PNG](favicon.png): 切り出し箱 `(433, 188, 567, 315)`（134×127）。背景で 134×134 にパディング。
- [favicon ICO](favicon.ico): 上記 PNG を LANCZOS で 16×16 / 32×32 / 48×48 に縮小した 32-bit フレーム。
- [概念図](olnm-concept.jpg): 切り出し箱 `(0, 408, 1536, 1024)`。アイコン／favicon のキャプション行より下、見出し「概念図」を含む。JPEG quality=95, subsampling=0 で再保存（ソースも JPEG）。
- [提供画像（原本）](olnm-overview.jpg): アイコン・favicon・概念図が同居していた見本ボード。README の表示には使いません。

GitHub Pages のビルド時に、正本の `favicon.ico` と `favicon.png` を `docs/assets/brand/` へコピーします。`docs/index.html` は公開ルート内の `assets/brand/favicon.ico` と `assets/brand/favicon.png` を相対参照します。生成コピーはリポジトリへ追加しません。
