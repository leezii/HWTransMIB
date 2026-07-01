# OctetString 模板预填 — 设计规格

日期:2026-07-01
状态:已通过头脑风暴评审,待写实现计划

## 背景与目标

构造表列 OID 时,用户需要为每个索引列输入值。对于 OctetString / IpAddress /
PhysAddress 等**字符串类索引列**,用户往往要输入结构固定的设备标识(如序列号、MAC
地址等),手输易错且繁琐。

本特性在这些列上提供**模板预填**:打开 OID 构造对话框时,自动把一个样式字符串预填
到输入框,用户只需修改其中的部分文字即可。

模板来自一个**外部资源文件**,由其他程序后期生成,放到固定文件位置后程序直接读取。
导入不一定是图形过程——用户把文件放到指定目录即可生效。

## 需求确认(头脑风暴结论)

| 决策点 | 选择 |
|---|---|
| 模板匹配方式 | **按列的完整 OID 精确匹配** |
| 未命中模板时 | **留空不预填**(与现状一致) |
| 资源文件格式 | **JSON** |
| 资源文件位置 | **`~/.hwtransmib/templates.json`**(与 config/favorites/history 同目录) |
| 模板形态 | **纯文本整串**,直接预填到 QLineEdit |
| 触发范围 | **所有字符串类索引列**(非整数、非枚举的列) |
| 预填时机 | **打开对话框时预填一次**,之后不干扰用户编辑 |

## 方案选择

采用**方案 A:UI 层内联最小改动 + 独立内核模块**。

考虑过的替代方案:

- **方案 B(服务层提供模板)**:在 `OidBuildService` 增加模板能力。否决——模板预填是
  UI 交互层的关注点,跟"构造/校验 OID"这个 service 核心职责无关,放进去会模糊
  service 的单一职责。
- **方案 C(持久化层扩展)**:把模板当作 `UserData` 的第五个 JSON 存储,提供 CRUD。
  否决——模板是**只读资源**(后期外部生成,程序只读不改),不需要 add/remove 接口,
  属于 YAGNI。

选择方案 A 的理由:模板的本质是"按 OID 查一个字符串"——一个纯数据查询,内核层一个
轻量模块最贴合;模板查询是无 Qt 依赖的纯函数,可单元测试;改动面最小、风险最低。

## 架构与分层

```
UI (oid_builder_dialog.py)
  └─ 打开对话框时,对每个字符串类索引列调 templates.lookup(col_oid)
       命中 → QLineEdit.setText(template)
       未命中 → 不动(留空)
  ↑ StringTemplateStore 通过 OidBuilderDialog 构造参数注入

kernel/string_templates.py  ← 新增
  └─ StringTemplateStore
       ├─ reload()           读 JSON,文件不存在/损坏 → 空表(不崩溃)
       └─ lookup(oid) → str | None   按 OID 精确查
```

沿用四层单向依赖(UI → 服务 → 内核 → 持久化)。`StringTemplateStore` 是内核层的纯数据
查询对象,不依赖 UI / 服务 / 持久化。文件路径通过构造注入,测试可传 `tmp_path`。

## 数据格式

**文件位置**:`~/.hwtransmib/templates.json`

```json
{
  "templates": [
    {
      "oid": "1.3.6.1.4.1.x.y.z",
      "template": "HWxxxxxx-某设备默认值示例",
      "comment": "某设备序列号列,HW 开头后跟 6 位数字"
    }
  ]
}
```

**字段说明**:

- `oid`(必填):索引列的完整 OID,作为匹配键。
- `template`(必填):预填模板字符串,纯文本。
- `comment`(可选):纯标注字段,**程序不读取、不影响任何逻辑**,仅供人工查阅理解。
  字段缺失或为空都完全正常。

**为什么用数组而非 `{oid: template}` 对象映射**:

- 后期由"别的程序生成",数组是顺序追加友好的格式,生成端 append 一条即可
- 对象映射要求生成端处理"已存在则覆盖"的合并语义,更复杂
- 查询时在 `reload()` 阶段一次性构建内存 dict(`oid → template`),查询 O(1),不影响性能
- 重复 OID 出现时取**数组中最后一条**(后写入覆盖先写入),语义明确
- 数组结构向后兼容,以后加更多标注字段不破坏旧文件

**字符编码**:UTF-8,JSON 写入 `ensure_ascii=False`(模板可能含中文/特殊符号)。

## 内核模块 `StringTemplateStore`

`kernel/string_templates.py`:

```python
class StringTemplateStore:
    """按列 OID 精确查 OctetString 预填模板。"""

    def __init__(self, path: Path) -> None:
        """path 指向 templates.json;通过构造注入便于测试传 tmp_path。"""

    def reload(self) -> None:
        """重新读盘构建内存表。文件不存在/损坏 → 空表(不抛异常)。"""

    def lookup(self, oid: str) -> str | None:
        """按列 OID 精确查模板;未命中返回 None。"""
```

**关键行为约定**:

1. **容错优先,绝不崩溃**。模板是辅助资源,任何读取问题都不能阻断 OID 构造主流程:
   - 文件不存在 → 空表
   - 文件存在但 JSON 解析失败 → 空表(记日志)
   - 某条数据缺 `oid` 或 `template` 字段 → 跳过该条,继续加载其余

2. **重复 OID 处理**:`reload()` 构建内存 dict 时,后出现的覆盖先出现的(数组顺序 =
   写入顺序,后写生效)。

3. **`comment` 字段**:加载时**完全不读取**,只为数据格式兼容性存在,不影响逻辑。

4. **`reload()` 与构造分离**:构造 `StringTemplateStore` 是零 I/O 的轻量操作;
   `reload()` 显式读盘。测试可构造后多次 `reload()`,也可测"文件中途被替换"场景。
   后期若加 GUI 导入按钮,`reload()` 是现成的刷新入口。

这是一个无状态查询对象(读盘后内存表只读),不是有生命周期的服务。

## UI 层集成

**改动点**:仅 `oid_builder_dialog.py` 的 `_build_ui()` 中,创建完每个索引列
`QLineEdit` 后,对字符串类列查模板预填。

**判断"字符串类索引列"**:直接读 `IndexSpec` 的元数据字段——**非整数、非枚举 = 字符串类**。
一个 `IndexSpec` 是字符串类,当且仅当:

- `is_integer == False`,且
- `named_values` 为空(无枚举)

直接在 UI 中用 `spec.is_integer == False and not spec.named_values` 判断,**不调用
`oid_builder` 的私有方法**。理由:预填资格判断发生在对话框打开、**尚无任何用户输入时**,
只能依据列的声明类型(`IndexSpec` 元数据);而 `oid_builder._coerce` 的分支判断依赖
**运行时输入值**(如 `_looks_integer` 的 isdigit 兜底),口径不能直接照搬到预填场景。
两者在"纯字符串类列"上结论一致(这类列最终都会走到字符串编码分支),故预填范围与编码
行为对齐,不引入两套口径。

**预填流程(在 `_build_ui` 的 spec 循环内)**:

```
创建 QLineEdit edit
attach completer(仅枚举列有)
判断该列是否字符串类(is_integer == False 且 named_values 为空)
  ├─ 是字符串类 → template = store.lookup(spec.column_oid)
  │              if template is not None: edit.setText(template)
  └─ 非字符串类(整数/枚举)→ 不查模板
edit.textChanged.connect(self._refresh)
```

**关键点**:

1. **预填用 `setText`,触发 `textChanged`**。这会顺带触发一次 `_refresh()`,对话框打开时
   预览区会**立刻显示模板被编码后的 OID**——符合预期的实时反馈,无需额外处理。

2. **预填时机 = 对话框构造时一次性**。`_build_ui` 在 `__init__` 里调用,只在打开时跑
   一次。之后用户的编辑由 `textChanged` 正常驱动,不会被覆盖。

3. **未命中模板的字符串列**:完全不动 `edit`,保持空,与现状一致。

## 依赖装配

**装配链**:

```
UserData (持有 ~/.hwtransmib/ base_dir)
   ↓ MainWindow 在创建 OidBuildService 的两处(_on_import / _reload_last),
   ↓ 顺带创建 StringTemplateStore
StringTemplateStore(path = base_dir / "templates.json").reload()
   ↓ 传给 OidBuilderDialog(新增构造参数 templates)
OidBuilderDialog._build_ui() 中 lookup()
```

**具体改动**:

1. **`UserData` 暴露 `base_dir`**:目前 `base_dir` 是 `_base` 私有属性,新增
   `@property base_dir` 暴露它。这是唯一对持久化层的改动——只暴露已有数据,不加新存储。

2. **`MainWindow` 持有 `StringTemplateStore`**:在创建 `_oid_svc` 的两处
   (`_on_import` 第 ~159 行 / `_reload_last` 第 ~323 行),紧跟着创建模板存储:
   ```python
   self._oid_svc = OidBuildService(parser=..., root=..., user_data=self._ud)
   self._templates = StringTemplateStore(self._ud.base_dir / "templates.json")
   self._templates.reload()
   ```
   时机与 `_oid_svc` / `_search_svc` 一致——都是 MIB 导入后、有 root 节点时才需要。

3. **`OidBuilderDialog` 新增参数**:`__init__` 增加 `templates: StringTemplateStore`。
   `_open_builder` 传入 `self._templates`。

**为什么模板 store 不放进 `OidBuildService`**:`OidBuildService` 职责是"编排 OID 构造
+ 记录历史"(行为编排);模板预填是 UI 交互层关注点,跟 service 核心职责无关。让 service
持有会模糊其单一职责。模板 store 直接由 UI 持有使用,路径最短、最清晰。

**加载时机**:MIB 导入后创建 store 时 `reload()` 一次。**不在每次打开对话框时重新读盘**
——模板是静态资源,一次加载到内存即可,查询走内存 dict(O(1))。后期若加 GUI 导入按钮,
导入后调一次 `reload()` 刷新。

## 错误处理

- `templates.json` 不存在 → 空表,所有字符串列保持空输入(完全等同现状)
- `templates.json` 存在但 JSON 非法 → 空表,记日志,不崩溃
- 某条数据缺 `oid` 或 `template` → 跳过该条,继续加载其余
- `lookup()` 永远不抛异常,未命中返回 `None`

## 测试策略

- **内核 `StringTemplateStore`(纯函数,脱离 GUI)**:
  - 正常加载 + lookup 命中/未命中
  - 文件不存在 → 空表
  - JSON 非法 → 空表
  - 某条缺字段 → 跳过该条
  - 重复 OID → 后者覆盖前者
  - `reload()` 刷新(文件中途替换)
- **UI 集成**:可选,构造 `OidBuilderDialog` 验证字符串类列预填、整数/枚举列不预填

## 不做的事(YAGNI)

- 不提供模板的图形化导入/编辑界面(后期"别的程序生成 + 放文件"已覆盖导入路径)
- 不把模板做成 `UserData` 的带 CRUD 的存储(模板只读)
- 不在每次打开对话框时重新读盘(静态资源,一次加载)
- 不做模板的占位符/变量替换(纯文本整串)
- 不对整数/枚举列预填模板(仅字符串类列)
