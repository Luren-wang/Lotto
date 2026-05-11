# 大樂透開獎號碼輸出

這個專案對應三個層級：

- `basic`：解析題目附件中的 HTML 片段，輸出第 115000049 期號碼。
- `latest`：爬取最近 50 期網頁，輸出最近一期號碼。
- `period`：爬取最近 50 期網頁，輸出指定期別號碼。

## 執行方式

```bash
python lottery.py basic
python lottery.py latest
python lottery.py period 115000049
python lottery.py period 049
```

目前預設資料來源為：

```text
https://lotto.hawo.tw/lotto/recent-50
```

如果網站格式改版，可以用 `--url` 換成相同表格結構的來源：

```bash
python lottery.py latest --url "https://example.com/recent-50"
```

## 測試

```bash
python -m unittest discover -s tests
```

## Render 部署

這個 repo 可以部署成 Render Web Service。

如果是用 `render.yaml` 建立服務，Render 會使用：

```text
Build Command: python -m unittest discover -s tests
Start Command: python app.py
Health Check Path: /health
```

如果服務已經在 Render Dashboard 手動建立，請確認 Start Command 設為：

```bash
python app.py
```

可用路由：

- `/`：顯示最近一期大樂透開獎號碼
- `/?period=115000049`：顯示指定期別
- `/api/latest`：最近一期 JSON
- `/api/period?period=115000049`：指定期別 JSON
- `/health`：Render health check

## 注意

指定期別功能目前查詢「最近 50 期」頁面中存在的期別。若要查更舊期別，需要改接有完整歷史資料的頁面或 API。
