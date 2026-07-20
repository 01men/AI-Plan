"""播种脚本：首次启动时执行一次（用 settings.seeded 标记）"""
import json
import random
from datetime import datetime, timedelta

J = lambda v: json.dumps(v, ensure_ascii=False)  # JSON 字段统一序列化（中文不转义）


def _now():
    return datetime.now().isoformat(timespec="seconds")


# ---------------- 组织主数据 ----------------
PLATFORMS = [
    ("战略平台", "PLT-STR", 43, "#4C6FFF"),
    ("产品营销平台", "PLT-MKT", 34, "#F2994A"),
    ("智造平台", "PLT-MFG", 177, "#27AE60"),
    ("研发平台", "PLT-RND", 64, "#9B51E0"),
    ("质量平台", "PLT-QA", 17, "#EB5757"),
]

DEPARTMENTS = {
    "战略平台": ["董事办", "总经办", "人力资源部", "流程革新部", "财务部", "审计部", "项目管理部", "行政部"],
    "产品营销平台": ["营销商务部", "市场部", "国际销售部", "国内销售部", "电商部", "营销项目部"],
    "智造平台": ["采购部", "生产部", "生管部", "生产技术部", "品管部", "PACK生产科"],
    "研发平台": ["研究院", "产品管理部", "研发部", "电动工具产品中心", "小家电产品中心"],
    "质量平台": ["测试实验室", "SQE管理部", "品保部"],
}

# (姓名, 部门, tier, 头衔, 方向)
PEOPLE = [
    ("董事长", "董事办", "boss", "董事长", "经营决策"),
    ("李乐平", "流程革新部", "coach", "流程革新部主管·内部教练", "流程革新/AI推广"),
    ("师圆圆", "流程革新部", "coach", "数字化项目负责人", "数字化转型"),
    ("付玉虎", "流程革新部", "coach", "AI应用开发工程师", "AI应用开发"),
    ("莫柳金", "人力资源部", "coach", "培训讲师", "AI应用培训"),
    ("戴栓", "流程革新部", "backbone", "流程骨干", "流程革新"),
    ("马进军", "项目管理部", "backbone", "项目管理骨干", "项目管理"),
    ("李丹", "人力资源部", "backbone", "人力资源骨干", "人力资源"),
    ("杨思严", "财务部", "backbone", "财务骨干", "财务管理"),
    ("徐婧", "人力资源部", "developer", "AI应用开发者", "人事/培训/招聘"),
    ("石杰", "流程革新部", "developer", "AI应用开发者", "流程革新/运维"),
    ("范丁鑫", "流程革新部", "developer", "AI应用开发者", "流程革新/运维"),
    ("吴慧婷", "财务部", "developer", "AI应用开发者", "财务全方向"),
    ("赵擎", "审计部", "developer", "AI应用开发者", "审计"),
    ("潘钰", "项目管理部", "developer", "AI应用开发者", "项目管理"),
    ("程冰梅", "行政部", "developer", "AI应用开发者", "行政事务"),
    ("贺晓晶", "营销商务部", "developer", "AI应用开发者", "商务助理"),
    ("张雨欣", "营销商务部", "developer", "AI应用开发者", "商务合同"),
    ("陈思思", "市场部", "developer", "AI应用开发者", "市场调研/外购比价"),
    ("胡鑫", "国际销售部", "developer", "AI应用开发者", "外贸销售/跟单/单证/包装资料"),
    ("谢荣浩", "国际销售部", "developer", "AI应用开发者", "外贸销售/跟单/单证/包装资料"),
    ("夏珍", "营销项目部", "developer", "AI应用开发者", "营销项目"),
    ("朱恬慧", "生产部", "developer", "AI应用开发者", "智造平台方向"),
    ("项芊茹", "生产部", "developer", "AI应用开发者", "智造平台方向"),
    ("李波", "采购部", "developer", "AI应用开发者", "采购"),
    ("刘能洁", "生产部", "developer", "AI应用开发者", "生产日报/异常闭环/设备点检"),
    ("沈嘉敏", "生管部", "developer", "AI应用开发者", "生管"),
    ("王晓忠", "生产技术部", "developer", "AI应用开发者", "生产技术"),
    ("吴昊轩", "研究院", "developer", "AI应用开发者", "技术研究"),
    ("贾廷慧", "产品管理部", "developer", "AI应用开发者", "产品管理"),
    ("何建强", "研发部", "developer", "AI应用开发者", "研发设计"),
    ("吴金韩", "研发部", "developer", "AI应用开发者", "研发设计"),
    ("祝吉江", "研发部", "developer", "AI应用开发者", "研发设计"),
    ("邱天", "研发部", "developer", "AI应用开发者", "研发设计"),
    ("陶晨浩", "研发部", "developer", "AI应用开发者", "研发设计"),
    ("高峰", "研发部", "developer", "AI应用开发者", "研发设计"),
    ("李晓辉", "测试实验室", "developer", "AI应用开发者", "测试实验"),
    ("陈航健", "SQE管理部", "developer", "AI应用开发者", "SQE"),
    ("顾兆恩", "品保部", "developer", "AI应用开发者", "品保"),
    ("徐露璐", "国际销售部", "staff", "业务使用人", "外贸业务"),
    ("张悦", "国际销售部", "staff", "业务使用人", "外贸业务"),
    ("李鑫", "产品管理部", "staff", "业务使用人", "产品管理"),
    ("徐文熠", "产品管理部", "staff", "业务使用人", "产品管理"),
    ("李建东", "品管部", "staff", "业务使用人", "品质管理"),
    ("王鑫", "品管部", "staff", "业务使用人", "品质管理"),
    ("梅鹏宇", "品管部", "staff", "业务使用人", "品质管理"),
    ("张卫", "研究院", "staff", "业务使用人", "技术研究"),
    ("林社然", "研究院", "staff", "业务使用人", "技术研究"),
]

# 部门 -> 该部门的开发者（用于 agent owner 指派）
DEPT_DEVELOPERS = {
    "人力资源部": ["徐婧"], "流程革新部": ["石杰", "范丁鑫"], "财务部": ["吴慧婷"],
    "审计部": ["赵擎"], "项目管理部": ["潘钰"], "行政部": ["程冰梅"],
    "营销商务部": ["贺晓晶", "张雨欣"], "市场部": ["陈思思"],
    "国际销售部": ["胡鑫", "谢荣浩"], "营销项目部": ["夏珍"],
    "生产部": ["朱恬慧", "项芊茹", "刘能洁"], "采购部": ["李波"], "生管部": ["沈嘉敏"],
    "生产技术部": ["王晓忠"], "研究院": ["吴昊轩"], "产品管理部": ["贾廷慧"],
    "研发部": ["何建强", "吴金韩", "祝吉江", "邱天", "陶晨浩", "高峰"],
    "测试实验室": ["李晓辉"], "SQE管理部": ["陈航健"], "品保部": ["顾兆恩"],
}

DEPT_CODE = {
    "董事办": "DSB", "总经办": "GM", "人力资源部": "HR", "流程革新部": "BPI",
    "财务部": "FIN", "审计部": "AUD", "项目管理部": "PMO", "行政部": "ADM",
    "营销商务部": "COM", "市场部": "MKT", "国际销售部": "INT", "国内销售部": "DOM",
    "电商部": "EC", "营销项目部": "MPM", "采购部": "PUR", "生产部": "PRD",
    "生管部": "PMC", "生产技术部": "PE", "品管部": "QC", "PACK生产科": "PACK",
    "研究院": "RES", "产品管理部": "PDM", "研发部": "RD", "电动工具产品中心": "PT",
    "小家电产品中心": "SA", "测试实验室": "LAB", "SQE管理部": "SQE", "品保部": "QA",
}

# 波次：战略平台+营销核心=1(8月)；营销深化+智造=2(9月)；研发+质量=3(10月)；其余=4
WAVE1_DEPTS = {"董事办", "总经办", "人力资源部", "流程革新部", "财务部", "审计部",
               "项目管理部", "营销商务部", "国际销售部"}
WAVE2_DEPTS = {"市场部", "国内销售部", "电商部", "营销项目部", "采购部", "生产部",
               "生管部", "生产技术部", "品管部", "PACK生产科"}
WAVE3_DEPTS = {"研究院", "产品管理部", "研发部", "电动工具产品中心", "小家电产品中心",
               "测试实验室", "SQE管理部", "品保部"}

C1, C2, C3, C4, C5, C6 = ("业务/项目助理", "智造运营/会议纪要", "BOM/物料",
                          "质量/制程异常分析", "研发测试/售后分析", "综合事务")

# (部门, 名称, 类别, 状态覆盖或None)
AGENTS = [
    ("董事办", "财务经营数字员工", C6, None),
    ("总经办", "总经办事务数字员工", C6, None),
    ("人力资源部", "人事数字员工", C6, None),
    ("人力资源部", "培训数字员工", C6, None),
    ("人力资源部", "招聘数字员工", C6, None),
    ("流程革新部", "流程革新数字员工", C6, None),
    ("流程革新部", "运维数字员工", C6, None),
    ("流程革新部", "项目管理智能体", "通用", "已上线"),
    ("财务部", "财务主管数字员工", C6, None),
    ("财务部", "应付会计数字员工", C6, None),
    ("财务部", "应收会计数字员工", C6, None),
    ("财务部", "总账会计数字员工", C6, None),
    ("财务部", "稽核会计数字员工", C6, None),
    ("财务部", "项目会计数字员工", C6, None),
    ("审计部", "审计专员数字员工", C6, None),
    ("项目管理部", "项目管理数字员工", C1, None),
    ("行政部", "行政文员数字员工", C6, None),
    ("营销商务部", "商务合同数字员工", C1, None),
    ("市场部", "市场调研数字员工", C1, None),
    ("市场部", "外购比价数字员工", C1, None),
    ("国际销售部", "外贸销售数字员工", C1, None),
    ("国际销售部", "外贸跟单数字员工", C1, "试点中"),
    ("国际销售部", "单证数字员工", C1, None),
    ("国际销售部", "包装资料数字员工", C1, None),
    ("国内销售部", "运营数字员工", C1, None),
    ("国内销售部", "售后跟进数字员工", C5, None),
    ("电商部", "电商运营数字员工", C1, None),
    ("营销项目部", "营销项目管理数字员工", C1, None),
    ("采购部", "采购数字员工", C3, None),
    ("生产部", "生产计划与日报数字员工", C2, None),
    ("生产部", "生产异常闭环数字员工", C2, None),
    ("生产部", "设备点检数字员工", C2, None),
    ("生产部", "会议纪要数字员工", C2, "试点中"),
    ("生管部", "生产计划数字员工", C2, None),
    ("生管部", "仓储库存数字员工", C3, None),
    ("生管部", "账实核对数字员工", C3, None),
    ("生产技术部", "设备管理数字员工", C2, None),
    ("生产技术部", "工艺改善数字员工", C2, None),
    ("生产技术部", "制程异常分析数字员工", C4, None),
    ("品管部", "品质检验数字员工", C4, None),
    ("品管部", "质量异常闭环数字员工", C4, None),
    ("品管部", "ERP质量录入校验数字员工", C4, None),
    ("PACK生产科", "PACK生产数字员工", C2, None),
    ("研究院", "研究院技术资料数字员工", C5, None),
    ("研究院", "实验报告数字员工", C5, None),
    ("产品管理部", "ERP编码数字员工", C3, None),
    ("产品管理部", "产品资料数字员工", C6, None),
    ("产品管理部", "样机流转数字员工", C6, None),
    ("产品管理部", "BOM物料数字员工", C3, "试点中"),
    ("研发部", "研发设计数字员工", C6, None),
    ("研发部", "图纸BOM校验数字员工", C3, None),
    ("研发部", "研发项目资料数字员工", C6, None),
    ("研发部", "研发测试分析助手", C5, "试点中"),
    ("电动工具产品中心", "产品项目数字员工", C1, None),
    ("小家电产品中心", "产品经理助理数字员工", C1, None),
    ("小家电产品中心", "小家电竞品分析数字员工", C1, None),
    ("测试实验室", "实验分析数字员工", C5, None),
    ("测试实验室", "测试报告数字员工", C5, None),
    ("SQE管理部", "SQE数字员工", C4, None),
    ("SQE管理部", "样品检测数字员工", C4, None),
    ("SQE管理部", "检验标准编制数字员工", C4, None),
    ("品保部", "品保质量数字员工", C4, None),
    ("品保部", "FMEA数字员工", C4, None),
    ("品保部", "计量管理数字员工", C4, None),
    ("品保部", "质量异常分析助手", C4, "试点中"),
]

PILOT_AGENTS = ["外贸跟单数字员工", "会议纪要数字员工", "BOM物料数字员工",
                "研发测试分析助手", "质量异常分析助手"]

CATEGORY_SKILLS = {
    C1: ["外贸单证生成", "合同要点检查", "待办分派"],
    C2: ["会议纪要", "生产日报生成", "待办分派"],
    C3: ["BOM三向比对", "缺料预警", "图纸校验"],
    C4: ["8D报告生成", "检验标准问答"],
    C5: ["实验数据分析", "售后问题归因"],
    C6: ["经营报表", "待办分派"],
    "通用": ["经营报表", "会议纪要", "待办分派"],
}

SKILLS = [
    ("会议纪要", "公开", "办公协同", "莫柳金", "会议录音/记录转结构化纪要并提取待办"),
    ("待办分派", "公开", "办公协同", "李乐平", "从纪要/群聊中提取待办并分派到人"),
    ("经营报表", "公开", "经营分析", "师圆圆", "经营数据自动汇总生成日报/周报/月报"),
    ("简历筛选", "公开", "人力资源", "徐婧", "按岗位要求自动筛选简历并排序"),
    ("人岗匹配分析", "公开", "人力资源", "徐婧", "候选人与岗位说明书多维匹配打分"),
    ("合同要点检查", "公开", "商务法务", "张雨欣", "检查交期/付款/质保等关键条款风险"),
    ("外贸单证生成", "公开", "外贸", "胡鑫", "自动生成发票/箱单/报关草单等单证"),
    ("唛头标签生成", "公开", "外贸", "谢荣浩", "按订单生成唛头与不干胶标签文件"),
    ("客户背景调研", "公开", "营销", "陈思思", "客户资信与背景信息自动调研汇总"),
    ("询价比价", "公开", "采购", "陈思思", "多供应商询价结果自动比价分析"),
    ("BOM三向比对", "公开", "研发", "贾廷慧", "ERP vs 图纸 vs 实物三向差异比对"),
    ("图纸校验", "公开", "研发", "何建强", "图纸要素与规范一致性自动校验"),
    ("缺料预警", "组织", "供应链", "沈嘉敏", "按生产计划计算缺料并给出采购建议"),
    ("生产日报生成", "组织", "智造", "刘能洁", "产线数据自动汇总生成生产日报"),
    ("库存异常预警", "组织", "供应链", "沈嘉敏", "库存账实差异与呆滞料自动预警"),
    ("8D报告生成", "组织", "质量", "顾兆恩", "按异常信息生成 D1-D8 框架的 8D 草稿"),
    ("检验标准问答", "组织", "质量", "陈航健", "检验标准库检索与智能问答"),
    ("实验数据分析", "组织", "研发", "李晓辉", "温升/电流/功率等实验数据对比分析"),
    ("售后问题归因", "组织", "质量", "顾兆恩", "售后维修记录聚类与归因分析"),
    ("数据脱敏", "组织", "治理", "付玉虎", "敏感字段自动识别与脱敏处理"),
]

KNOWLEDGE_SPACES = [
    ("战略平台财务空间", "群晖DS925+", "8T", "财务部", "财务经营数据"),
    ("战略平台空间", "群晖DS925+", "8T", "战略平台", "战略与组织"),
    ("产品营销平台空间", "群晖DS925+", "8T", "产品营销平台", "营销与客户"),
    ("研发平台空间", "群晖DS925+", "8T", "研发平台", "研发与产品"),
    ("智造质量平台空间", "群晖DS925+", "12T", "智造与质量平台", "智造供应链与质量"),
    ("榕器创共享空间", "群晖DS925+", "8T", "榕器创", "共享制造与数字化赋能"),
]

# (空间名, [(标题, 密级, 标签, 上传人)])
DOCUMENTS = {
    "战略平台财务空间": [
        ("财务经营分析月报模板", "L3", "财务,报表", "吴慧婷"),
        ("应收应付台账结构说明", "L3", "财务,台账", "杨思严"),
        ("费用报销制度汇编", "L2", "制度", "杨思严"),
    ],
    "战略平台空间": [
        ("NAS文件存储与数据管理规范", "L2", "规范,知识管理", "师圆圆"),
        ("AI数智化企业应用推广行动方案", "L2", "战略,AI", "李乐平"),
        ("组织架构与岗位说明书", "L3", "组织,HR", "李丹"),
    ],
    "产品营销平台空间": [
        ("客户资料库", "L3", "客户,外贸", "胡鑫"),
        ("外贸单证模板包", "L2", "单证,外贸", "谢荣浩"),
        ("市场调研报告汇编", "L2", "市场,调研", "陈思思"),
    ],
    "研发平台空间": [
        ("电机技术资料库", "L2", "电机,技术", "吴昊轩"),
        ("AI编程开发管理规范 v0.1", "L2", "规范,开发", "付玉虎"),
        ("BOM编制与变更管理规范", "L2", "BOM,规范", "贾廷慧"),
        ("产品认证资料清单", "L3", "认证", "徐文熠"),
        ("L4 核心配方·示例（仅示意）", "L4", "配方,核心机密", "吴昊轩"),
    ],
    "智造质量平台空间": [
        ("8D报告库", "L3", "质量,8D", "顾兆恩"),
        ("检验标准库", "L3", "质量,检验", "陈航健"),
        ("会议纪要SOP", "L1", "SOP,会议", "刘能洁"),
        ("设备点检标准", "L2", "设备,点检", "王晓忠"),
        ("L4 核心工艺参数·示例（仅示意）", "L4", "工艺,核心机密", "王晓忠"),
    ],
    "榕器创共享空间": [
        ("数字员工运营月报", "L1", "运营,AI", "师圆圆"),
        ("AI应用案例集", "L1", "案例,AI", "莫柳金"),
        ("数据脱敏操作指引", "L2", "治理,脱敏", "付玉虎"),
    ],
}

# (阶段, 月份, 名称, 负责人, 节点类型, 状态)
MILESTONES = [
    ("筑基期", "2026-08", "NAS知识库部署", "付玉虎", "hybrid", "进行中"),
    ("筑基期", "2026-08", "五大保障机制发布", "师圆圆", "human", "进行中"),
    ("筑基期", "2026-08~09", "教练团组建与培训", "莫柳金", "hybrid", "未开始"),
    ("筑基期", "2026-08", "首批5场景立项", "李乐平", "human", "未开始"),
    ("筑基期", "2026-09", "首批场景MVP开发", "付玉虎", "agent", "未开始"),
    ("筑基期", "2026-09", "覆盖率自动统计上线", "项目管理智能体", "agent", "未开始"),
    ("筑基期", "2026-09", "第一轮达标扩围", "师圆圆", "hybrid", "未开始"),
    ("推广期", "2026-10", "第二轮扩围", "师圆圆", "hybrid", "未开始"),
    ("推广期", "2026-10", "标杆项目打造", "李乐平", "hybrid", "未开始"),
    ("推广期", "2026-08~12", "周报月报自动归档", "项目管理智能体", "agent", "未开始"),
    ("推广期", "2026-11", "第三轮扩围", "师圆圆", "hybrid", "未开始"),
    ("推广期", "2026-11", "标杆固化", "李乐平", "human", "未开始"),
    ("推广期", "2026-09~11", "月度成果分享", "莫柳金", "hybrid", "未开始"),
    ("深化期", "2026-12", "年终复盘与考核", "董事长", "human", "未开始"),
    ("深化期", "2026-12", "2027年度规划", "师圆圆", "human", "未开始"),
]

INCENTIVES = [
    ("火花奖", "陈思思", "外购比价场景提案被采纳，月度优秀创意", 800, "已评定"),
    ("银齿轮奖", "胡鑫", "外贸跟单数字员工试点季度达标，节省工时突出", 8000, "已评定"),
    ("金扳手奖", "付玉虎", "年度AI应用开发贡献奖：搭建平台底座与多个数字员工", 30000, "已评定"),
]

REIMBURSEMENTS = [
    ("胡鑫", "智谱GLM", 1200000, 360.0, "待平台长审批", 1),
    ("石杰", "百度文心", 800000, 240.0, "已完成", 3),
]

REDLINE_NOTE = "AI应用六大红线"  # 审计用

# 首批 5 个重点场景：(部门, 关联agent, 名称, 效益, 动作列表, 描述)
PILOT_SCENARIOS = [
    ("国际销售部", "外贸跟单数字员工", "外贸订单跟单自动化", "12.24万/年",
     ["订单资料自动整理（邮件/钉钉提取归档至NAS）", "ERP下单草稿生成", "唛头/不干胶标签生成",
      "合同关键条款检查（交期/付款/质保）", "发货跟踪", "客户资料归档"],
     "外贸订单从邮件接收到发货归档的全流程资料自动整理与单证生成"),
    ("生产部", "会议纪要数字员工", "会议纪要与待办闭环", "7.56万/年",
     ["会议录音转结构化纪要", "待办事项提取与分派", "OPL台账更新", "钉钉催办", "周报/月报自动生成"],
     "生产例会录音自动转纪要、提取待办并跟踪闭环"),
    ("产品管理部", "BOM物料数字员工", "BOM三向比对与缺料预警", "10.8万/年",
     ["BOM三向比对（ERP vs 图纸 vs 实物）", "物料规格变更通知", "供应商交付跟踪预警",
      "缺料计算与采购建议", "退货/金额核对"],
     "BOM 三向一致性自动比对，缺料提前预警并给出采购建议"),
    ("品管部", "质量异常分析助手", "质量异常结构化与8D草稿", "11.88万/年",
     ["异常单结构化", "历史问题匹配（相似度>80%自动推荐方案）", "8D报告草稿生成",
      "检验标准问答", "缺陷归类统计"],
     "质量异常单自动结构化，匹配历史方案并生成 8D 报告草稿"),
    ("研发部", "研发测试分析助手", "研发测试数据与售后归因分析", "11.52万/年",
     ["测试数据整理", "温升/电流/功率对比", "售后问题归因", "维修记录归档", "客户报告生成"],
     "研发测试数据自动整理对比，售后问题聚类归因"),
]

# 各部门扩围场景：(部门, 名称, 优先级)  —— 动作按名称生成通用三段式
EXTRA_SCENARIOS = [
    ("董事办", "经营数据日报自动生成", "中"), ("董事办", "战略会议纪要归档", "低"),
    ("总经办", "公文起草辅助", "中"), ("总经办", "日程与会议协调", "低"), ("总经办", "经营驾驶舱数据汇总", "中"),
    ("人力资源部", "招聘简历筛选", "中"), ("人力资源部", "岗位说明书生成", "中"), ("人力资源部", "培训需求调研汇总", "低"),
    ("流程革新部", "流程文件智能问答", "中"), ("流程革新部", "运维工单自动分派", "中"), ("流程革新部", "流程优化建议生成", "低"),
    ("财务部", "发票识别与三单匹配", "中"), ("财务部", "应收账款账龄分析", "中"), ("财务部", "费用报销智能审核", "低"),
    ("审计部", "审计抽样辅助", "中"), ("审计部", "审计底稿自动生成", "低"),
    ("项目管理部", "项目周报自动汇总", "中"), ("项目管理部", "项目风险预警", "中"),
    ("行政部", "办公用品申领审批辅助", "低"), ("行政部", "会议纪要转写", "低"), ("行政部", "车辆调度统计", "低"),
    ("营销商务部", "商务合同条款审查", "中"), ("营销商务部", "报价单自动生成", "中"),
    ("市场部", "竞品分析", "中"), ("市场部", "外购询价比价", "中"), ("市场部", "行业资讯日报", "低"),
    ("国际销售部", "客户背景调研", "中"), ("国际销售部", "信用证条款审核", "中"), ("国际销售部", "邮件自动翻译与摘要", "低"),
    ("国内销售部", "销售数据日报", "中"), ("国内销售部", "售后工单分类", "中"), ("国内销售部", "经销商对账辅助", "低"),
    ("电商部", "商品标题优化", "低"), ("电商部", "评价情感分析", "中"), ("电商部", "大促活动复盘", "低"),
    ("营销项目部", "营销项目排期", "中"), ("营销项目部", "渠道费用核销辅助", "低"),
    ("采购部", "供应商对账", "中"), ("采购部", "采购价格趋势分析", "中"), ("采购部", "供应商交期预警", "中"),
    ("生产部", "生产异常闭环跟踪", "中"), ("生产部", "设备点检异常汇总", "中"), ("生产部", "班组绩效统计", "低"),
    ("生管部", "物料齐套检查", "中"), ("生管部", "呆滞料分析", "中"), ("生管部", "库存周转分析", "低"),
    ("生产技术部", "设备故障知识库问答", "中"), ("生产技术部", "工艺参数优化建议", "低"), ("生产技术部", "点检计划自动生成", "低"),
    ("品管部", "检验数据自动录入", "中"), ("品管部", "不良品统计分析", "中"), ("品管部", "客诉8D跟踪", "中"),
    ("PACK生产科", "PACK装配记录归档", "低"), ("PACK生产科", "PACK产能日报", "中"),
    ("研究院", "技术资料智能检索", "中"), ("研究院", "实验报告模板生成", "低"), ("研究院", "文献摘要", "低"),
    ("产品管理部", "ERP编码查重", "中"), ("产品管理部", "产品资料一致性检查", "中"), ("产品管理部", "样机流转跟踪", "低"),
    ("研发部", "图纸与BOM一致性检查", "中"), ("研发部", "技术变更影响分析", "中"), ("研发部", "设计规范问答", "低"),
    ("电动工具产品中心", "项目进度自动跟踪", "中"), ("电动工具产品中心", "产品认证资料管理", "低"),
    ("小家电产品中心", "竞品功能对比", "中"), ("小家电产品中心", "产品定义文档辅助", "低"),
    ("测试实验室", "测试报告自动生成", "中"), ("测试实验室", "实验数据自动分析", "中"), ("测试实验室", "测试用例库问答", "低"),
    ("SQE管理部", "供应商来料异常分析", "中"), ("SQE管理部", "检验标准自动编制", "中"), ("SQE管理部", "供应商绩效评分", "低"),
    ("品保部", "FMEA辅助编制", "中"), ("品保部", "计量器具台账管理", "低"), ("品保部", "质量月报自动生成", "中"),
]


def _default_actions(name):
    return [f"{name}·资料采集与结构化", f"{name}·智能分析与生成", f"{name}·人工确认后归档"]


def run_seed(conn) -> bool:
    """若已播种则跳过；否则全量播种。返回是否执行了播种。"""
    if conn.execute("SELECT value FROM settings WHERE key='seeded'").fetchone():
        return False

    from app import engine  # 延迟导入，避免循环依赖

    now = _now()
    dept_id, person_id, agent_id = {}, {}, {}

    # 1. 平台/部门/人员
    for name, code, hc, color in PLATFORMS:
        pid = conn.execute(
            "INSERT INTO platforms(name,code,headcount,color) VALUES(?,?,?,?)",
            (name, code, hc, color)).lastrowid
        for d in DEPARTMENTS[name]:
            did = conn.execute(
                "INSERT INTO departments(platform_id,name) VALUES(?,?)", (pid, d)).lastrowid
            dept_id[d] = did

    for name, dept, tier, title, direction in PEOPLE:
        person_id[name] = conn.execute(
            "INSERT INTO people(dept_id,name,role_title,tier,direction,status) VALUES(?,?,?,?,?,'在职')",
            (dept_id[dept], name, title, tier, direction)).lastrowid

    # 2. 数字员工
    rr = {}  # 部门内开发者轮询计数
    dept_first_agent = {}  # 部门 -> 该部门第一个数字员工 id（扩围场景绑定用）
    for dept, name, category, st_override in AGENTS:
        wave = 1 if dept in WAVE1_DEPTS else 2 if dept in WAVE2_DEPTS else 3 if dept in WAVE3_DEPTS else 4
        status = st_override or ("开发中" if wave in (1, 2) else "规划中")
        devs = DEPT_DEVELOPERS.get(dept, [])
        owner = None
        if devs:
            owner = person_id[devs[rr.get(dept, 0) % len(devs)]]
            rr[dept] = rr.get(dept, 0) + 1
        idx = conn.execute("SELECT COUNT(*) c FROM agents WHERE dept_id=?", (dept_id[dept],)).fetchone()["c"] + 1
        code = f"DE-{DEPT_CODE[dept]}-{idx:02d}"
        skills = CATEGORY_SKILLS.get(category, CATEGORY_SKILLS[C6])
        desc = f"{dept}·{name}：面向{category}场景的数字员工（第{wave}波次）"
        agent_id[name] = conn.execute(
            "INSERT INTO agents(dept_id,name,code,category,description,status,owner_id,wave,skills,"
            "tasks_done,hours_saved,accuracy) VALUES(?,?,?,?,?,?,?,?,?,0,0,0)",
            (dept_id[dept], name, code, category, desc, status, owner, wave, J(skills))).lastrowid
        dept_first_agent.setdefault(dept, agent_id[name])
    # 项目管理智能体作为平台底座：已上线并带有历史产出
    conn.execute("UPDATE agents SET tasks_done=30, hours_saved=62.5, accuracy=98.0 WHERE name='项目管理智能体'")

    # 3. 场景（首批试点 + 扩围）
    scenario_id = {}
    for dept, agent, name, benefit, actions, desc in PILOT_SCENARIOS:
        scenario_id[name] = conn.execute(
            "INSERT INTO scenarios(dept_id,agent_id,name,description,priority,batch,status,expected_benefit,actions)"
            " VALUES(?,?,?,?,'高','首批','试点中',?,?)",
            (dept_id[dept], agent_id[agent], name, desc, benefit, J(actions))).lastrowid
    # 扩围场景绑定责任数字员工：本部门第一个数字员工，无则平台任一员工兜底
    fallback_agent = next(iter(agent_id.values()))
    for dept, name, prio in EXTRA_SCENARIOS:
        benefit = "预估5万/年" if prio == "中" else "预估1.5万/年"
        conn.execute(
            "INSERT INTO scenarios(dept_id,agent_id,name,description,priority,batch,status,expected_benefit,actions)"
            " VALUES(?,?,?,? ,?,'扩围','待立项',?,?)",
            (dept_id[dept], dept_first_agent.get(dept, fallback_agent),
             name, f"{dept}扩围场景：{name}", prio, benefit, J(_default_actions(name))))

    # 4. 技能 / 知识库 / 文档
    for name, scope, cat, owner, desc in SKILLS:
        conn.execute("INSERT INTO skills(name,scope,category,owner_name,description) VALUES(?,?,?,?,?)",
                     (name, scope, cat, owner, desc))
    space_id = {}
    for name, device, cap, dept, domain in KNOWLEDGE_SPACES:
        space_id[name] = conn.execute(
            "INSERT INTO knowledge_spaces(name,device,capacity,dept_name,domain) VALUES(?,?,?,?,?)",
            (name, device, cap, dept, domain)).lastrowid
        for title, level, tags, uploader in DOCUMENTS[name]:
            conn.execute(
                "INSERT INTO documents(space_id,title,level,tags,uploaded_by,created_at) VALUES(?,?,?,?,?,?)",
                (space_id[name], title, level, tags, uploader, now))

    # 5. 里程碑 / 激励 / 报销
    for phase, month, name, owner, ntype, st in MILESTONES:
        conn.execute("INSERT INTO milestones(phase,month,name,owner,node_type,status) VALUES(?,?,?,?,?,?)",
                     (phase, month, name, owner, ntype, st))
    for typ, nominee, reason, amount, st in INCENTIVES:
        conn.execute("INSERT INTO incentives(type,nominee,reason,amount,status,created_at) VALUES(?,?,?,?,?,?)",
                     (typ, nominee, reason, amount, st, now))
    for applicant, provider, tokens, amount, st, step in REIMBURSEMENTS:
        conn.execute("INSERT INTO reimbursements(applicant,provider,tokens,amount,status,step,created_at)"
                     " VALUES(?,?,?,?,?,?,?)", (applicant, provider, tokens, amount, st, step, now))

    # 6. 工作区：总经办·经营驾驶舱 + 5 个试点项目工作区
    def add_ws(name, wtype, scenario, creator):
        wid = conn.execute(
            "INSERT INTO workspaces(name,type,scenario_id,created_by,created_at) VALUES(?,?,?,?,?)",
            (name, wtype, scenario, creator, now)).lastrowid
        return wid

    def add_member(wid, mtype, mid):
        conn.execute("INSERT INTO workspace_members(workspace_id,member_type,member_id) VALUES(?,?,?)",
                     (wid, mtype, mid))

    def add_msg(wid, stype, sid, sname, zone, mtype, content, payload=None, ts=None):
        conn.execute(
            "INSERT INTO messages(workspace_id,sender_type,sender_id,sender_name,zone,msg_type,content,payload,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (wid, stype, sid, sname, zone, mtype, content, J(payload) if payload else None, ts or now))

    cockpit = add_ws("总经办·经营驾驶舱", "部门", None, person_id["董事长"])
    for n in ["董事长", "师圆圆", "李乐平"]:
        add_member(cockpit, "human", person_id[n])
    add_member(cockpit, "agent", agent_id["项目管理智能体"])
    add_msg(cockpit, "system", None, "系统", "discussion", "text",
            "经营驾驶舱工作区已创建，项目管理智能体将在此发布每日经营日报。")

    # 各试点工作区的主持人与关联人员
    pilot_humans = {
        "外贸订单跟单自动化": ["胡鑫", "谢荣浩", "徐露璐"],
        "会议纪要与待办闭环": ["刘能洁", "朱恬慧"],
        "BOM三向比对与缺料预警": ["贾廷慧", "李鑫"],
        "质量异常结构化与8D草稿": ["顾兆恩", "李建东"],
        "研发测试数据与售后归因分析": ["何建强", "李晓辉"],
    }
    pilot_req = {
        "外贸订单跟单自动化": "@外贸跟单数字员工 请整理本周德国客户订单资料并生成唛头",
        "会议纪要与待办闭环": "@会议纪要数字员工 请把昨天生产例会的录音整理成纪要并提取待办",
        "BOM三向比对与缺料预警": "@BOM物料数字员工 请对 JT-5120 产品做 BOM 三向比对并给出缺料预警",
        "质量异常结构化与8D草稿": "@质量异常分析助手 请把 7 月客户投诉的异响问题结构化并生成 8D 草稿",
        "研发测试数据与售后归因分析": "@研发测试分析助手 请对比新款角磨温升测试数据并分析售后发热投诉归因",
    }
    for dept, agent, sname, benefit, actions, desc in PILOT_SCENARIOS:
        humans = pilot_humans[sname]
        wid = add_ws(f"试点项目·{sname}", "项目", scenario_id[sname], person_id[humans[0]])
        for h in humans:
            add_member(wid, "human", person_id[h])
        add_member(wid, "agent", agent_id[agent])
        base = datetime.now() - timedelta(hours=30)
        add_msg(wid, "system", None, "系统", "discussion", "text",
                f"试点项目工作区已创建：{sname}（{benefit}）。成员已就位，开始试点运行。",
                ts=base.isoformat(timespec="seconds"))
        add_msg(wid, "human", person_id[humans[0]], humans[0], "discussion", "text",
                f"各位，{sname}试点今天启动，预期效益 {benefit}，请数字员工随时待命。",
                ts=(base + timedelta(hours=1)).isoformat(timespec="seconds"))
        add_msg(wid, "human", person_id[humans[0]], humans[0], "agent", "text", pilot_req[sname],
                ts=(base + timedelta(hours=2)).isoformat(timespec="seconds"))
        # 生成一个待审核任务及其交付物卡片消息（复用引擎逻辑）
        engine.dispatch(conn, wid, agent_id[agent], humans[0], pilot_req[sname],
                        creator_id=person_id[humans[0]])

    # 7. 试点 agent 近 14 天指标
    rng = random.Random(42)
    today = datetime.now().date()
    for aname in PILOT_AGENTS:
        aid = agent_id[aname]
        total_tasks, total_hours, accs = 0, 0.0, []
        for i in range(14):
            d = today - timedelta(days=13 - i)
            td = rng.randint(0, 6)
            hs = round(rng.uniform(0.5, 3.0), 1)
            tc = round(rng.uniform(1.0, 8.0), 2)
            ac = round(rng.uniform(93, 99), 1)
            conn.execute(
                "INSERT INTO metrics_daily(date,agent_id,tasks_done,hours_saved,token_cost,accuracy)"
                " VALUES(?,?,?,?,?,?)", (d.isoformat(), aid, td, hs, tc, ac))
            total_tasks += td
            total_hours += hs
            accs.append(ac)
        conn.execute("UPDATE agents SET tasks_done=?, hours_saved=?, accuracy=? WHERE id=?",
                     (total_tasks, round(total_hours, 1), round(sum(accs) / len(accs), 1), aid))

    # 8. 初始审计（含已评定种子激励的评定留痕）
    for actor, action, target, detail in [
        ("系统", "平台初始化", "platform", "数据库建表并完成首次播种"),
        ("师圆圆", "发布", "五大保障机制", "组织/制度/激励/费用/红线保障机制发布"),
        ("李乐平", "立项申报", "首批5场景", "首批 5 个重点场景进入试点"),
        ("董事长", "激励评定", "陈思思", "火花奖 ¥800 评定通过：外购比价场景提案被采纳"),
        ("董事长", "激励评定", "胡鑫", "银齿轮奖 ¥8000 评定通过：外贸跟单试点季度达标"),
        ("董事长", "激励评定", "付玉虎", "金扳手奖 ¥30000 评定通过：年度AI应用开发贡献"),
    ]:
        conn.execute("INSERT INTO audits(actor,action,target,detail,created_at) VALUES(?,?,?,?,?)",
                     (actor, action, target, detail, now))

    conn.execute("INSERT INTO settings(key,value) VALUES('seeded','1')")
    conn.commit()
    return True
