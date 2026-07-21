# 交大学生成绩管理系统

这是一个独立的本机教学演示站点，外观看起来是普通的学生成绩管理系统，但后端保留了多种常见 Web 安全问题，便于在课程作业中演示攻击行为如何产生 IDS 可检测日志。它与正常版 `交大学生成绩管理系统` 分离运行，正常版系统不受影响。

页面不会显示攻击方式、训练场景、靶场按钮、审计日志或 IDS 导出入口。演示者可以通过浏览器地址栏、接口工具或脚本直接访问业务接口来触发漏洞。

## 功能

- 学生用户登录后页面默认显示自己的成绩，并可按课程名称查询单科成绩。
- 教师用户登录后可以查看全部学生成绩，并登记或修改成绩。
- 后端保留审计日志和 IDS 兼容 CSV 导出接口，用于联动检测系统。
- 站点绑定本机地址 `127.0.0.1:8001`，用于本地课程演示。

## 运行

从 `network intrusion detection system` 目录进入该子项目后启动：

```bash
cd "交大学生成绩管理系统_vuln_lab"
python app.py
```

默认访问地址：

```text
http://127.0.0.1:8001
```

## 演示账号

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 学生 | 2024001 | 123456 |
| 学生 | 2024002 | 123456 |
| 学生 | 2024003 | 123456 |
| 教师 | teacher | teacher123 |

## 可演示问题

### 越权查询

学生登录后，页面默认只加载本人记录，但后端接口信任 `student_id` 查询参数。登录学生 `2024001 / 123456` 后直接请求：

```text
/api/grades?student_id=2024002
```

响应会返回 `2024002` 的成绩记录。

### SQL 注入形态查询

登录学生 `2024001 / 123456` 后，可以在学生端的课程查询框输入下列内容，或直接请求：

```text
/api/grades?course=%E4%BF%A1%E6%81%AF%E5%AE%89%E5%85%A8%E5%AF%BC%E8%AE%BA%27%20or%201=1--
```

响应中的成绩记录会包含 `2024001`、`2024002` 和 `2024003`。

### 存储型 XSS

教师账号可以登记课程名称。由于成绩列表前端直接拼接返回字段，教师录入包含 HTML/脚本形态的课程名称后，其他用户查看成绩列表时会渲染该内容。

## 演示脚本

启动站点后，可以使用本机脚本触发常见演示行为：

```bash
python scripts/demo_attacks.py all
```

也可以只运行单项：

```bash
python scripts/demo_attacks.py idor
python scripts/demo_attacks.py sqli
python scripts/demo_attacks.py xss
python scripts/demo_attacks.py bruteforce
python scripts/demo_attacks.py export
python scripts/demo_attacks.py reset
```

脚本默认只访问 `http://127.0.0.1:8001`，并会拒绝非本机目标地址。

页面会每 3 秒刷新当前成绩查询，因此脚本写入的成绩或课程记录会自动显示在已打开的页面中。

## IDS 联动

靶场服务会把真实网站访问请求持续写入 `data/access_log.csv`，包括登录、成绩查询、攻击脚本请求、HTTP 状态码和请求路径。演示时先运行靶场并触发攻击，再打开 IDS 的“日志分析”页面，点击“分析靶场实时日志”，IDS 会直接读取这份运行时日志并生成告警。

系统仍保留后端接口用于课程检测联动：

- `GET /api/lab/audit`：查看最近审计记录。
- `GET /api/lab/export-log`：导出兼容 IDS 解析器的 CSV 日志，可作为手动上传备用方式。
- `POST /api/lab/reset`：恢复种子用户和成绩数据，并清空运行时访问日志。

这些入口不会显示在页面上。

## 测试

在项目根目录运行：

```bash
PYTHONPATH="C:/Users/tmp/Desktop/信安科技创新/network intrusion detection system/交大学生成绩管理系统_vuln_lab;C:/Users/tmp/Desktop/信安科技创新/network intrusion detection system" python -m pytest "C:/Users/tmp/Desktop/信安科技创新/network intrusion detection system/交大学生成绩管理系统_vuln_lab/tests"
```

## 数据文件

- `data/seed_users.json`：用户种子数据。
- `data/seed_grades.json`：成绩种子数据。
- `data/scenarios.json`：用于 IDS 导出的攻击特征日志数据。
- `data/audit_log.jsonl`：本地审计日志。
- `data/access_log.csv`：靶场服务运行时写入的真实访问日志，IDS 可直接分析。
- `data/exported_logs.csv`：最近一次导出的 IDS 兼容日志。
