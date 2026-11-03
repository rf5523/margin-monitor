融資水位儀表板（GitHub Actions + GitHub Pages）

1. 在 GitHub 建立新的 Public repository（例如 margin-monitor）。
2. 把本資料夾全部內容上傳到該 repository
   （包含隱藏資料夾 .github，網頁上傳請直接把整個資料夾內容拖進去，
    或用 Git / GitHub Desktop）。
3. Settings -> Pages -> Source 選 "Deploy from a branch"，
   Branch 選 main，資料夾選 /docs，按 Save。
4. Actions 分頁 -> 左側選 update-data -> Run workflow，手動執行一次，
   第一次會補抓近 45 天資料（約 3 分鐘）。
5. 完成後網址為 https://你的帳號.github.io/repository名稱/
