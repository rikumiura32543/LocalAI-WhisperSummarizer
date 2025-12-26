# 🎨 デザインシステム

目標管理システムのUIデザインガイドライン

## カラーパレット（6色厳守）

```css
--color-white: #FFFFFF;      /* 背景・テキスト */
--color-black: #222222;      /* メインテキスト */
--color-primary: #4CAF50;    /* プライマリボタン・アクセント */
--color-danger: #D32F2F;     /* エラー・警告 */
--color-gray-light: #F5F5F5; /* 軽いセパレーター・背景 */
--color-gray-medium: #E0E0E0; /* ボーダー・無効状態 */
```

## タイポグラフィ

```css
/* フォントファミリー */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;

/* フォントサイズ */
--font-size-xs: 12px;    /* 補足テキスト */
--font-size-sm: 13px;    /* 小テキスト */
--font-size-base: 14px;  /* 基本テキスト */
--font-size-md: 16px;    /* 中見出し */
--font-size-lg: 18px;    /* 大見出し */
--font-size-xl: 20px;    /* タイトル */

/* 行間 */
--line-height-tight: 1.2;   /* 見出し用 */
--line-height-normal: 1.5;  /* 本文用 */
--line-height-relaxed: 1.6; /* 長文用 */

/* フォントウェイト */
--font-weight-normal: 400;
--font-weight-medium: 500;
--font-weight-bold: 600;
```

## スペーシングシステム

```css
/* 8pxベースのスペーシング */
--space-xs: 4px;
--space-sm: 8px;
--space-md: 12px;
--space-base: 16px;
--space-lg: 20px;
--space-xl: 24px;
--space-2xl: 32px;
--space-3xl: 40px;
```

## コンポーネント仕様

### ボタン

```css
/* 共通仕様 */
min-height: 44px;           /* WCAG 2.1 AA準拠 */
min-width: 44px;
padding: 12px 16px;
border: none;
border-radius: 0;           /* フラットデザイン */
box-shadow: none;           /* フラットデザイン */
font-size: 14px;
cursor: pointer;
transition: background-color 0.2s ease;

/* プライマリボタン */
background-color: #4CAF50;
color: #FFFFFF;

/* プライマリボタン（ホバー） */
background-color: #45a049;

/* セカンダリボタン */
background-color: #E0E0E0;
color: #222222;

/* セカンダリボタン（ホバー） */
background-color: #d0d0d0;

/* デンジャーボタン */
background-color: #D32F2F;
color: #FFFFFF;

/* デンジャーボタン（ホバー） */
background-color: #c62828;

/* 無効状態 */
background-color: #E0E0E0;
color: #999999;
cursor: not-allowed;
```

### カード

```css
background: #FFFFFF;
border: 1px solid #E0E0E0;
border-radius: 0;           /* フラットデザイン */
box-shadow: none;           /* フラットデザイン */
padding: 20px;
margin-bottom: 20px;

/* カードヘッダー */
font-size: 18px;
font-weight: 600;
margin-bottom: 15px;
padding-bottom: 10px;
border-bottom: 2px solid #4CAF50;
color: #222222;
```

### テーブル

```css
width: 100%;
border-collapse: collapse;

/* ヘッダー */
th {
  background-color: #222222;
  color: #FFFFFF;
  font-weight: 600;
  padding: 12px 8px;
  text-align: left;
  border-bottom: 2px solid #E0E0E0;
}

/* セル */
td {
  padding: 12px 8px;
  color: #222222;
  border-bottom: 1px solid #E0E0E0;
}

/* 行ホバー */
tr:hover {
  background-color: #F5F5F5;
}
```

### フォーム要素

```css
/* 入力フィールド */
input, textarea, select {
  width: 100%;
  padding: 12px;
  border: 1px solid #E0E0E0;
  border-radius: 0;           /* フラットデザイン */
  box-shadow: none;           /* フラットデザイン */
  font-size: 14px;
  min-height: 44px;           /* WCAG 2.1 AA準拠 */
}

/* フォーカス状態 */
input:focus, textarea:focus, select:focus {
  outline: none;
  border-color: #4CAF50;
}

/* 無効状態 */
input:disabled, textarea:disabled, select:disabled {
  background-color: #F5F5F5;
  color: #999999;
  cursor: not-allowed;
}
```

### ナビゲーション（サイドバー）

```css
width: 250px;
background-color: #222222;
color: #FFFFFF;

/* メニューアイテム */
a {
  display: block;
  padding: 12px 20px;
  min-height: 44px;          /* WCAG 2.1 AA準拠 */
  color: #FFFFFF;
  text-decoration: none;
  transition: background-color 0.2s ease;
}

/* ホバー */
a:hover {
  background-color: #333333;
}

/* アクティブ */
a.active {
  background-color: #4CAF50;
}
```

## 評価表示の色分け（200点満点）

```css
/* 優秀: 160点以上 */
.evaluation.high {
  background-color: #E8F5E9;  /* 薄い緑 */
  color: #2E7D32;              /* 濃い緑 */
}

/* 標準: 130-159点 */
.evaluation.medium {
  background-color: #FFF9C4;  /* 薄い黄色 */
  color: #F57F17;              /* 濃い黄色 */
}

/* 要改善: 130点未満 */
.evaluation.low {
  background-color: #FFEBEE;  /* 薄い赤 */
  color: #C62828;              /* 濃い赤 */
}

/* 評価バッジ共通スタイル */
.evaluation {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 0;           /* フラットデザイン */
  font-weight: 600;
}
```

## レイアウト

### グリッドシステム

```css
/* コンテナ */
.container {
  display: flex;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 16px;
}

/* グリッド（2カラム） */
.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

/* グリッド（3カラム） */
.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

/* グリッド（4カラム） */
.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
```

### レスポンシブブレークポイント

```css
/* モバイル（デフォルト） */
@media (max-width: 767px) {
  /* スタック表示 */
  .grid-2, .grid-3, .grid-4 {
    grid-template-columns: 1fr;
  }

  /* サイドバーを上部に */
  .container {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
  }
}

/* タブレット */
@media (min-width: 768px) and (max-width: 1023px) {
  /* 2カラム表示 */
  .grid-3, .grid-4 {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* デスクトップ */
@media (min-width: 1024px) {
  /* 通常通り表示 */
}
```

## デザイン原則

### 1. 完全フラットデザイン
- `box-shadow: none` を全要素に適用
- `border-radius: 0` を全要素に適用
- グラデーション禁止
- 影・立体感の表現禁止

### 2. 44px最小タッチサイズ（WCAG 2.1 AA準拠）
- 全てのクリック可能要素は44px × 44px以上
- ボタン、リンク、フォーム要素に適用

### 3. 絵文字禁止
- UIに絵文字を使用しない
- テキストとアイコン文字のみ使用
- 記号は許可（例: ×、+、-、✓）

### 4. モバイルファーストデザイン
- デフォルトはモバイル表示
- メディアクエリで画面サイズを拡張

### 5. アクセシビリティ
- コントラスト比4.5:1以上（WCAG AA準拠）
- フォーカス状態の明示
- キーボード操作対応
- スクリーンリーダー対応のセマンティックHTML

### 6. カラーパレット厳守
- 定義された6色以外使用禁止
- 透明度は許可（例: rgba(34, 34, 34, 0.5)）

### 7. 一貫性
- 同じ機能には同じスタイルを適用
- スペーシングは8pxの倍数を使用
- フォントサイズは定義された6種類のみ使用
