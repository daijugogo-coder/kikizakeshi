Worklog.md（2026-01-15 時点）
Kikizakeshi – Location & Season Based Recommendation Upgrade
1. 背景

飲料（主に酒）に合う料理・食材の提案ロジックを改善するため、
「地域 × 季節 × 店舗カスタム」 の概念を導入。

ただし、ハードコーディングされた季節・食材テーブルは持たないという方針。

地域・気候・季節の知識は LLM側に委譲し、Python側は最小限のメタ情報だけ提供する構成へ移行。

2. 実装方針（確定版）
■ ハードコーディングしない

「北海道の夏はとうもろこし」「ハワイは通年～」などの知識は Python 側には一切持たない。

季節テーブルや旬の辞書は持たず、LLM に任せる。

■ Python側が行う最低限の処理

locale から大まかな地域/気候の推定（hemisphere）

現在の月 から季節ラベル（spring/summer/autumn/winter）を算出

ハワイ向けは後述の JSON による「location_hint」で調整可能

store_custom.json をロードして、店舗ごとの推し情報を user_payload に含める

■ LLM に渡す情報（新仕様）

locale

cuisine

hemisphere

season

extracted（ラベル情報）

ocr_snippet

store_custom（店舗カスタム） ← New

LLM はこれらの情報を基に
**「季節感・地域感・店舗感を踏まえた“食材ベース”の提案」**を生成する。

3. store_custom.json の導入（新機能）
■ 目的

“店舗ごとの推しやローカル文化”を反映させるオーバーレイレイヤー。

Python は触らずに JSON のみを編集すれば挙動を変えられるため、メンテナンス性が非常に高い。

本番は空の JSON を使い、デモ時だけ内容を入れる運用が可能。

■ ハワイ向けサンプル（デモ用）

以下の JSON を store_custom.json として配置すると、
ハワイの店舗向けの自然なペアリング提案が返される。

{
  "store_name": "Hawaii Sake & Wine Shop",
  "location_hint": "Honolulu, Hawaii. Warm climate all year.",
  "special_ingredients": [
    {
      "id": "hawaiian_poke",
      "label": "Hawaiian poke (fresh tuna with savory sauce)",
      "best_with": [
        "light beer",
        "crisp white wine",
        "chilled junmai ginjo sake"
      ],
      "season": "all_year"
    },
    {
      "id": "kalua_pork",
      "label": "Kalua pork (smoky roasted pork)",
      "best_with": [
        "amber beer",
        "light red wine",
        "medium-bodied sake"
      ],
      "season": "all_year"
    },
    {
      "id": "lomi_lomi_salmon",
      "label": "Lomi-lomi salmon",
      "best_with": [
        "sparkling wine",
        "light white wine",
        "chilled sake"
      ],
      "season": "all_year"
    }
  ],
  "special_messages": [
    "Because Hawaii is warm all year, avoid recommending heavy hot stews.",
    "Highlight refreshing dishes with seafood and fresh vegetables.",
    "If the product looks local, gently add one Hawaiian-style pairing option."
  ]
}

4. main.py 改修（今回実施した内容）
■ 追加ポイント（全て実装済み）

store_custom.json のロードロジックを追加
（try/catch 付き、未存在なら空のデフォルト辞書で動作）

グローバル変数 STORE_CUSTOM に保持

user_payload に store_custom を注入

system_prompt に store_custom の説明と利用ルールを追記

実装全体は安全寄りで、JSON が壊れていてもアプリは落ちない

5. 次にやるべきこと（移行後）

動作確認（ハワイの店舗向け JSON を入れた状態）
→ 食材ベースの自然な提案が返ってくるかチェック。

他地域の JSON のテンプレを作る（必要なら生成可）

Washington

California

Japan: 北海道 / 九州 など

最終的に本番用は空 JSON にする
→ 店舗導入時だけ JSON を用意して渡す運用。

6. 仕様上の重要な原則

Python は “知識を持たない”

LLM が “旬・地域・季節” を判断する

店舗カスタムは 外部 JSON のみ

拡張性・運用性・説明力に優れる構成

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
