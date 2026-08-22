/**
 * AOMERA Academy の資料申込を Google Sheets に追記する Web App。
 *
 * 1. Google Apps Script のプロジェクトを作成し、このコードを貼り付ける。
 * 2. Google Sheets を作成し、スクリプト プロパティに SPREADSHEET_ID を追加する。
 * 3. 必要なら SHEET_NAME も追加する（未設定時は「資料申込」）。
 * 4. 「ウェブアプリ」としてデプロイし、実行ユーザーを自分、アクセスを全員にする。
 * 5. 発行された URL を academy/index.html の data-google-script-url に設定する。
 */
function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  const requestId = String((e && e.parameter && e.parameter.requestId) || '');

  try {
    const properties = PropertiesService.getScriptProperties();
    const spreadsheetId = properties.getProperty('SPREADSHEET_ID');
    const sheetName = properties.getProperty('SHEET_NAME') || '資料申込';
    if (!spreadsheetId) {
      throw new Error('SPREADSHEET_ID is not configured.');
    }

    const data = e.parameter || {};
    if (!data.name || !data.email) {
      throw new Error('Name and email are required.');
    }
    const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
    let sheet = spreadsheet.getSheetByName(sheetName);
    if (!sheet) {
      sheet = spreadsheet.insertSheet(sheetName);
    }
    const submittedAt = data.submittedAt
      ? Utilities.formatDate(new Date(data.submittedAt), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss')
      : Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');

    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['受付日時', 'お名前', 'メールアドレス', '学習目的・ご要望', '送信元']);
      sheet.getRange(1, 1, 1, 5).setFontWeight('bold').setBackground('#e8f0fe');
      sheet.setFrozenRows(1);
    }

    sheet.appendRow([
      submittedAt,
      toSheetCell_(data.name),
      toSheetCell_(data.email),
      toSheetCell_(data.purpose || '（未入力）'),
      toSheetCell_(data.source)
    ]);
    SpreadsheetApp.flush();

    return createBrowserResponse_({
      type: 'aomera-resource-submission',
      requestId: requestId,
      ok: true
    });
  } catch (error) {
    console.error(error && error.stack ? error.stack : String(error));
    return createBrowserResponse_({
      type: 'aomera-resource-submission',
      requestId: requestId,
      ok: false,
      error: String(error)
    });
  } finally {
    lock.releaseLock();
  }
}

/**
 * 初回デプロイ前にエディタから一度実行し、Google Sheets 権限を承認する。
 * 成功すると、実行ログに対象スプレッドシート名が表示される。
 */
function authorizeSpreadsheetAccess() {
  const spreadsheetId = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
  if (!spreadsheetId) {
    throw new Error('SPREADSHEET_ID is not configured.');
  }

  const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  console.log('Google Sheets authorization succeeded: ' + spreadsheet.getName());
}

function toSheetCell_(value) {
  const text = String(value || '');
  return /^[=+\-@]/.test(text) ? "'" + text : text;
}

function createBrowserResponse_(result) {
  const message = JSON.stringify(result).replace(/</g, '\\u003c');
  return HtmlService
    .createHtmlOutput('<!doctype html><meta charset="utf-8"><script>window.top.postMessage(' + message + ', "*");<\/script>')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
