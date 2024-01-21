#!/bin/bash

cd /tmp
# LuaLaTeX コマンドの定義（非対話的モードで実行）
lualatex_cmd="lualatex -interaction=nonstopmode"
input_tex_file="$1"
# LuaLaTeX を実行して PDF を生成
$lualatex_cmd "$input_tex_file" #> /dev/null 2>&1

# LuaLaTeX の終了ステータスをチェック
if [ $? -ne 0 ]; then
    echo "LuaLaTeX でエラーが発生しました"
    exit 1
fi

echo "PDF が正常に生成されました"
exit 0


