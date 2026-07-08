# PanSou Python

基于 FastAPI + SQLite 的网盘搜索聚合后端与移动端搜索页。

## 功能

- 本地 SQLite 资源库（分类、资源、热搜词、搜索日志）
- 插件化搜索框架
- 默认对接 fish2018/pansou 上游 API（需本地启动 8888 端口服务）
- 搜索聚合与按网盘类型分类
- 链接有效性检测
- 移动端响应式搜索首页

## 快速开始

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

访问：http://localhost:8000/

## 环境变量

复制 `.env.example` 为 `.env` 后按需修改。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接 | `sqlite:///./pansou.db` |
| `UPSTREAM_PANSOU_ENABLED` | 是否启用上游 API | `true` |
| `UPSTREAM_PANSOU_BASE_URL` | fish2018/pansou 服务地址 | `http://127.0.0.1:8888` |
| `NATIVE_PLUGINS_ENABLED` | 是否启用原生网页抓取插件 | `false` |

## Docker

```bash
docker compose up -d --build
```
