# Kikizakeshi (OCR + LLM) Project

## 概要

`Kikizakeshi` は、Google Cloud Vision APIを利用して、写真やテキストから日本酒やその他の商品情報を抽出するアプリケーションです。ユーザーがバーコードやラベルの写真を提供することで、AI（OpenAI GPT-4）を使って詳細な商品情報や楽しみ方を多言語で提供します。

### 主な機能
- バーコードやラベル写真から商品情報を抽出（OCR機能）
- 多言語対応で、ロケールに応じた言語で回答
- 酒類以外の商品にも柔軟に対応（回答調整可能）
- クラウド環境（Cloud Run）で動作

---

## 動作環境

このアプリケーションは **Google Cloud Run** 上で動作しています。**Google Cloud Vision API**（OCR処理）を使用して、画像からテキストを抽出し、**OpenAI GPT-4** を用いて商品情報や説明を生成します。

- **Cloud Run** を利用するため、サービスアカウントの設定が必要です。
- OCRの動作は、`google-cloud-vision`ライブラリによって提供され、Google Cloudの認証は自動で処理されます。

---

## 環境設定

### 必要な環境変数

- `OPENAI_API_KEY`: OpenAI APIのAPIキー
- `OPENAI_MODEL`: 使用するモデル（例: `gpt-4.1-mini`）
- `OPENAI_BASE_URL`: OpenAI APIのベースURL（通常は `https://api.openai.com/v1`）

**Cloud Run上で動作しているため、Google Cloudのサービスアカウントを使用した自動認証が行われ、`GOOGLE_APPLICATION_CREDENTIALS` 環境変数の設定は不要です。**

### GCP環境のサービスアカウント設定

Cloud Runにデプロイしたアプリケーションでは、サービスアカウントが自動的に認証を行うため、**`GOOGLE_APPLICATION_CREDENTIALS`** の設定は不要です。ただし、Google Cloud Vision APIを使用するために適切なAPIのアクセス権が付与されていることを確認してください。

---

## インストール方法

ローカル開発環境で実行する場合の手順は以下の通りです。

1. 必要なパッケージをインストールします：

   ```bash
   pip install -r requirements.txt
