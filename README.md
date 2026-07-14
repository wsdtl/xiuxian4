# xiuxian4

`xiuxian4` 是聊天文字游戏服务的自下而上重建版本。当前公共底座版本为 `public-foundation.v6`，
已经建立正式名录、双世界皮肤和第一个玩家命令。

## 当前地基

- FastAPI 应用工厂与生命周期管理
- 服务端单实例保护
- 配置驱动的业务模块加载
- QQ 开放平台单机器人 Webhook 驱动器
- 用于测试和巡检的本地命令驱动器
- 公共命令上下文、依赖注入、命令守卫和显式回复目标
- 跨驱动 `message.Message` 文档、图片、图标和动作协议
- 协议与存储无关的 Gameplay 标签、属性、Effect、Ability、条件和 Trigger 规则内核
- 显式规则版本、Ruleset、逻辑时间、确定性随机源和标准失败码
- 任意数量、多历史版本的世界皮肤投影目录
- 已封板的战斗底座 `combat.foundation.v2`
- 已封板的物品与物资底座 `inventory.foundation.v1`
- 已封板的角色与成长底座 `character.foundation.v3`
- 已封板的原子装配底座 `loadout.foundation.v2`
- 已封板的武器底座 `weapon.foundation.v2`
- 已封板的装备底座 `equipment.foundation.v1`
- 已封板的价值评估底座 `valuation.foundation.v1`
- 已封板的随机物品化底座 `itemization.foundation.v1`
- 已封板的临时队伍底座 `party.foundation.v1`
- 已封板的账号与归属底座 `account.foundation.v1`
- 已封板的经济账本底座 `economy.foundation.v1`
- 已封板的统一奖励结算底座 `reward.foundation.v1`
- 已封板的权益凭证与兑付底座 `grant.foundation.v1`
- 已封板的持久化联合事务底座 `persistence.foundation.v6`
- 已封板的内容包统一组装底座 `content.foundation.v2`
- 已封板的时间与周期底座 `cycle.foundation.v1`
- 异步行动槽与生命周期底座 `action.foundation.v1`
- 已封板的铭刻底座 `inscription.foundation.v1`
- 已封板的掉落与保底底座 `loot.foundation.v1`
- 已封板的世界空间与区域状态底座 `world.foundation.v1`
- 已封板的交换契约底座 `exchange.foundation.v1`
- 已封板的活动实例底座 `activity.foundation.v1`
- 已封板的组织与社会关系底座 `social.foundation.v1`
- 已封板的事实投影、通知与排名底座 `projection.foundation.v1`
- 伤害、治疗、护盾、控制、状态、干预器和复合数值公式
- 多目标、回合时间线、目标约束、动态参战和结构化战报事实
- 可堆叠物资、独立实例、容器、来源批次、预约托管和原子资产事务
- 物品消耗、Ability、角色资源、事务防重与 Outbox 的联合提交
- 五项角色核心值、显式成长曲线、永久特征和开放来源贡献
- 角色、装备、组织与场景贡献到 `RuleEntity` 的统一投影
- 一个武器槽、六个装备槽及与库存共同回滚的装卸事务
- 武器品质、显式等级表、经验成长和受约束随机属性
- 开放随机装备、分段套装能力、生成后品质和不可变生成凭据
- 单件内在价值、整套价值、边际价值和多维价值向量
- 多套配装保存与背包满载时的原子一键切换
- 队长、成员、站位、准备状态、社会邀请接力和战斗阵营投影
- QQ 多身份到稳定内部账号的自动归并、冲突保护和防重放
- SQLite 结构版本、CAS 聚合快照、数据库事务防重和 Outbox
- 货币、物品、角色与武器奖励的跨领域数据库联合提交
- 版本化内容包、依赖拓扑、隐藏引用审计、统一冻结和运行内容指纹
- 日、周、月、固定间隔和显式活动窗口，以及可重启的周期补偿工作队列
- 主行动、委托行动和即时行动的冻结快照、到期结算、领取、取消与中断
- 武器、装备和武器 Ability 的实例铭刻、原名投影与联合事务防重
- 永久事实日志、可归零重建的投影检查点、通知收件箱和不可变排名快照
- 掉落审计与保底、任意世界拓扑、交换冻结、活动参与和通用组织关系
- QQ Markdown/按钮键盘与本地测试结果渲染器
- 回调签名、时间窗、请求体限制、有界队列、事件去重和安全重试
- 脱敏结构日志与真实 QQ 协议测试组件

## 环境要求

- Windows 与 PowerShell
- Python 3.11 或更高版本
- 用于真实联调的 QQ 开放平台机器人应用
- 能转发到本地服务端口的公网 HTTPS 地址

## 初始化

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

至少需要在 `.env` 中填写：

```dotenv
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
SERVER_SSL_CERTFILE=certs/example_bundle.pem
SERVER_SSL_KEYFILE=certs/example.key
QQ_BOT_APP_ID=机器人应用ID
QQ_BOT_SECRET=机器人密钥
DATABASE_PATH=game/database/xiuxian4.db
```

`.env`、证书、私钥和机器人密钥禁止提交到 Git。

## 启动

Windows 本地启动：

```powershell
.\start.bat
```

Docker 或 Linux 容器启动：

```sh
sh ./start.sh
```

Dockerfile 可以使用：

```dockerfile
CMD ["sh", "./start.sh"]
```

`start.sh` 不负责安装依赖。镜像构建阶段应先执行 `pip install -r requirements.txt`。可以通过环境变量 `PYTHON_BIN` 指定容器内的 Python 命令。

QQ 回调路径由 `QQ_EVENT_PATH` 配置，默认是 `/qq/events`：

```text
https://公网域名:端口/qq/events
```

同一项目只能运行一个服务实例。重复启动会被单实例锁拒绝，避免定时任务和消息队列重复执行。

## 加载模块

当前只自动加载框架初始化模块和可删除的协议测试组件：

```dotenv
ROUTER_MODULE_GROUPS=["auto", "组件测试"]
ROUTER_MODULES=["game.app"]
ROUTER_FOLDERS=[]
ROUTER_GROUPS=["game.cmd"]
ROUTER_CHILD_FOLDERS=[]
```

`game/cmd/` 是命令与 HTTP 接口总路由。`ROUTER_GROUPS=["game.cmd"]` 会注册总 HTTP 路由，并导入
各个中文二级组件完成消息命令注册；`组件测试/` 继续提供可删除的 QQ 现场联调能力。

当前第一个正式命令是：

```text
创建角色
创建角色 名称
```

未显式提供名称时使用消息携带的平台昵称。`game/cmd/角色/__init__.py` 只处理命令注册，实际业务与
回复放在同目录的 `service.py`；数据库联合提交和服务装配留在内部底座。

## 注册命令

不依赖平台私有事实的命令可以通过公共 `MessageHandler` 注册，使同一回调被所有启用的消息驱动器消费：

```python
from launch.adapter import MessageHandler, manager
from message import M


@MessageHandler.handler(cmd="状态", priority=100, block=True)
async def show_status(client_id: str) -> None:
    reply = (
        M.document()
        .section("运行状态", icon="status")
        .row(("阶段", 1), ("状态", "正常"))
        .build()
    )
    await manager.send(reply, client_id)
```

业务回调中注入的 `manager` 也是公共管理器。普通游戏命令入口只需声明业务参数，例如
`message`；身份、昵称和回复目标由组件服务读取当前公共上下文。QQ 与本地驱动器只在各自内部完成
身份规整，组件仍然只注册一次。

## 消息协议

业务必须构造 `message.Message`，不能直接返回 Markdown 字符串或平台 payload：

```python
from message import Action, M

reply = (
    M.document()
    .header("示例对象 Lv1")
    .inline_section("通知", "任务已完成", icon="system")
    .section("资源列表", icon="inventory")
    .row(("数量", 3), ("状态", "可用"))
    .action(Action("view", "查看", "查看 示例物品", behavior="send"))
    .build()
)

await manager.send(reply, client_id)
```

公共适配器管理器会拒绝 QQ 原生字典。平台原生 payload 只允许存在于驱动器内部和协议探针。

## QQ 联调

启用 `组件测试.QQ协议测试` 后，群聊发送：

```text
@机器人 QQ协议测试
```

测试面板覆盖回调、即发、回填、引用、Markdown、图片和身份字段。完整操作方法见 [QQ 协议测试组件](组件测试/QQ协议测试/QQ协议测试说明.md)。

## 运行测试

```powershell
Get-ChildItem test\*_test.py | Sort-Object Name | ForEach-Object {
  .venv\Scripts\python.exe -X utf8 -B $_.FullName
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

## 说明文档

- [游戏核心边界](game/core/核心边界说明.md)
- [核心架构门禁](design/核心架构门禁说明.md)
- [正式内容层](game/content/正式内容层说明.md)
- [具体游戏规则](game/rules/具体游戏规则说明.md)
- [游戏应用装配](game/应用装配说明.md)
- [角色组件](game/cmd/角色/说明.md)
- [公共底座封板说明](design/公共底座封板说明.md)
- [真正核心封板清单](design/真正核心封板清单.md)
- [游戏设计宪章](design/游戏设计宪章.md)
- [Gameplay 规则内核](game/core/gameplay/规则内核说明.md)
- [战斗底座封板说明](game/core/gameplay/combat/战斗底座封板说明.md)
- [物品与物资底座说明](game/core/gameplay/inventory/物品与物资底座说明.md)
- [角色与成长底座说明](game/core/gameplay/character/角色与成长底座说明.md)
- [装配底座说明](game/core/gameplay/loadout/装配底座说明.md)
- [武器底座说明](game/core/gameplay/weapon/武器底座说明.md)
- [装备底座说明](game/core/gameplay/equipment/装备底座说明.md)
- [价值评估底座说明](game/core/gameplay/valuation/价值评估底座说明.md)
- [随机物品化底座说明](game/core/gameplay/itemization/随机物品化底座说明.md)
- [队伍底座说明](game/core/gameplay/party/队伍底座说明.md)
- [账号与归属底座说明](game/core/account/账号与归属底座说明.md)
- [经济账本底座说明](game/core/gameplay/economy/经济账本底座说明.md)
- [统一奖励结算底座说明](game/core/gameplay/rewards/统一奖励结算底座说明.md)
- [权益凭证与兑付底座说明](game/core/gameplay/grants/权益凭证与兑付底座说明.md)
- [持久化联合事务底座说明](game/core/persistence/持久化联合事务底座说明.md)
- [内容包统一组装底座说明](game/core/gameplay/content/内容包统一组装底座说明.md)
- [时间与周期底座说明](game/core/gameplay/cycles/时间与周期底座说明.md)
- [异步行动底座说明](game/core/gameplay/actions/异步行动底座说明.md)
- [铭刻底座说明](game/core/gameplay/inscription/铭刻底座说明.md)
- [掉落与保底底座说明](game/core/gameplay/loot/掉落与保底底座说明.md)
- [世界空间与区域状态底座说明](game/core/gameplay/world/世界空间与区域状态底座说明.md)
- [交换契约底座说明](game/core/gameplay/exchange/交换契约底座说明.md)
- [活动实例与参与结算底座说明](game/core/gameplay/activities/活动实例与参与结算底座说明.md)
- [组织与社会关系底座说明](game/core/gameplay/social/组织与社会关系底座说明.md)
- [事实投影、通知与排名底座说明](game/core/gameplay/projections/事实投影通知与排名底座说明.md)
- [战斗内核](game/core/gameplay/combat/战斗内核说明.md)
- [战斗编排](game/core/gameplay/combat/战斗编排说明.md)
- [高级特效机制](game/core/gameplay/combat/高级特效机制说明.md)
- [公共消息协议](message/消息协议说明.md)
- [应用与通信架构](launch/架构说明.md)
- [通信驱动器接入模板](launch/adapter/驱动器模板.md)
- [QQ 驱动器](launch/adapter/qq/QQ驱动器说明.md)
- [QQ 协议测试组件](组件测试/QQ协议测试/QQ协议测试说明.md)

只有项目根目录保留入口文件 `README.md`；其他说明文档的文件名、正文、代码注释和使用说明全部使用中文。

## 架构边界

- `game/` 统一收纳公共游戏核心、具体游戏产品和本地游戏数据库。
- `game/core/` 是公共游戏核心的唯一命名空间，对外导入路径为 `game.core`。
- `message/` 是协议中立地基，不能导入 `launch`、QQ 驱动器或业务包。
- `game/core/gameplay/` 是规则中立地基，不能导入 `launch`、`message`、数据库或具体玩法。
- `game/core/account/` 是平台协议中立的账号与归属地基，不能导入 `launch`、QQ 驱动、数据库或 Gameplay。
- `game/core/persistence/` 可以适配领域快照，但领域包不能反向导入持久化实现。
- `game/content/` 只承载稳定名录、世界皮肤和统一装配，只能依赖 Gameplay 公共契约。
- `game/rules/` 只保存跨组件复用的英文具体游戏规则，不放中文组件业务文件。
- `game/app.py` 负责组装内容、规则、持久化服务和启动生命周期。
- `game/cmd/` 承接命令与对应组件业务；二级组件的 `__init__.py` 只注册，`service.py` 负责调用底座和展示。
- 只有 `game/cmd/` 的二级组件目录使用中文；Python 文件名和代码标识符统一使用英文。
- `组件测试/` 只存放可删除的联调与协议测试，禁止依赖游戏代码。
- `launch/` 只负责应用运行与通信基础设施，不能导入未来修仙业务包。
- 未来业务组件通过 `MessageHandler` 注册命令，通过公共 `manager` 发送统一消息对象。
- 平台身份、原始事件、原生 payload 和发送目标只能存在于对应驱动器包内。
- 脱离当前消息上下文发送时必须提供明确 `ReplyTarget`，框架不会根据历史消息猜测目标。
