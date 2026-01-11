## 2026-01-11 – Kikizakeshi Progress

- **Main.py**:
  - IP情報を使って国/地域/緯度から気候（tropical/subtropical）を推定し、LLMのpromptに追加
  - OCRでEAN-13(JAN)を抽出し、`item_id` として返却（チェックデジット検証付き）
  - LLM出力に`language`, `answer`, `tags`, `item_id`, `notes`を拡張
  - 非アルコールのアイテムについては断定せず、誤飲やアレルギーの危険話題に触れない
  - tropical/subtropical の場合、「冬の煮込み系」を避けるルールをpromptで追加

- **index.html**:
  - Clerkの回答に「Prefer / Not prefer」ボタンを追加（tagsが付与された場合のみ）
  - IndexedDB（kikizakeshi_local）にユーザーの評価を保存
  - ユーザーの選好（dry, fruity, strong, fresh, heavy）を過学習しないステップで更新

- **style.css**:
  - Prefer / Not preferボタンを追加するスタイルを末尾に追加

- **進行状況**:
  - 現在、ローカルでの動作確認を行い、特に「アルコールアイテム」のタグ付けや「非アルコールアイテム」の取り扱いが正しく動作するかを確認中。
  
- **次のステップ**:
  - ローカル確認後、集約先プロジェクトへのデプロイ予定。
