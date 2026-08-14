/**
 * 潜机问诊：guided-intake 九层问诊的字段与问题库。
 *
 * 依据 lever-gaokao/references/guided-intake.md 的九层问诊结构编码：
 * 第 1 层硬信息 → 第 2 层学生本人 → 第 3 层家庭约束 → 第 4 层家长期望 →
 * 第 5 层风险偏好与不可接受项 → 第 6 层长期目标 → 第 7 层价值观 →
 * 第 8 层宏观变量 → 第 9 层输出偏好。
 *
 * 设计原则（遵循 guided-intake）：不一次性抛出过多问题，优先补齐最影响判断的资料。
 * 字段按优先级分 required（决定方案边界）/ important（决定策略）/ optional（可延后）。
 */

export interface IntakeQuestion {
  /** 字段键（collected 字典的 key） */
  field: string
  /** 所属层（1-9） */
  layer: number
  /** 字段中文名 */
  label: string
  /** 给用户的问题（口语化，遵循 communication-style） */
  question: string
  priority: 'required' | 'important' | 'optional'
  /** 可选项（供 ask_user_question 展示） */
  options?: string[]
}

export const LAYER_NAMES: Record<number, string> = {
  1: '硬信息',
  2: '学生本人',
  3: '家庭约束',
  4: '家长期望',
  5: '风险偏好与不可接受项',
  6: '长期目标',
  7: '价值观',
  8: '宏观变量',
  9: '输出偏好',
}

export const QUESTIONS: IntakeQuestion[] = [
  // ---- 第 1 层：硬信息（required，决定方案边界）----
  { field: 'province', layer: 1, label: '省份', priority: 'required',
    question: '考生在哪个省份参加高考？' },
  { field: 'year', layer: 1, label: '年份', priority: 'required',
    question: '哪一年参加高考？' },
  { field: 'subject_type', layer: 1, label: '科类/选科', priority: 'required',
    question: '选科组合或科类是什么？（如 物理+化学+生物 / 历史类 / 理科）' },
  { field: 'score', layer: 1, label: '总分', priority: 'required',
    question: '高考总分是多少？' },
  { field: 'rank', layer: 1, label: '位次', priority: 'required',
    question: '全省位次（一分一段）大概是多少？位次比分数更能判断可达性。' },
  { field: 'batch', layer: 1, label: '批次', priority: 'required',
    question: '目标批次是什么？（本科批 / 专科批 / 提前批 / 专项）' },

  // ---- 第 2 层：学生本人（important，决定适配）----
  { field: 'subject_strength', layer: 2, label: '学科强弱', priority: 'important',
    question: '哪些科目明显强、哪些明显弱？（尤其注意：选科偏理但实际更擅长语言/表达的情况）' },
  { field: 'student_preference', layer: 2, label: '学生偏好', priority: 'important',
    question: '学生本人有没有明确想去的城市、想学的专业，或特别排斥的方向？' },
  { field: 'career_imagination', layer: 2, label: '职业想象', priority: 'important',
    question: '对未来职业有什么想象？（如教师/医生/公务员/技术/自由职业；这个想象来自长期兴趣还是近期热门讨论？）' },
  { field: 'distance_tolerance', layer: 2, label: '离家接受度', priority: 'important',
    question: '对离家远、城市大小、气候和生活方式的接受度如何？' },

  // ---- 第 3 层：家庭约束（important，决定现实边界）----
  { field: 'budget', layer: 3, label: '家庭预算', priority: 'required',
    question: '每年学费和生活费的上限大概是多少？能否接受民办或中外合作办学？' },
  { field: 'region_constraint', layer: 3, label: '地域约束', priority: 'important',
    question: '是否必须在本省或某个城市读书？这是硬性照护需求，还是更安心的偏好？' },
  { field: 'family_support', layer: 3, label: '家庭支持', priority: 'important',
    question: '家庭能否支持考研、复读、异地实习或长期备考？家里有什么行业经验或资源？' },

  // ---- 第 4 层：家长期望（important，记录但不盲从）----
  { field: 'family_expectation', layer: 4, label: '家长期望', priority: 'important',
    question: '家长最看重什么：学校名气、专业就业、离家近、稳定，还是城市机会？最担心什么？' },
  { field: 'family_student_conflict', layer: 4, label: '家校差异', priority: 'important',
    question: '家长的想法和学生本人的想法有冲突吗？主要分歧在哪？' },

  // ---- 第 5 层：风险偏好与不可接受项（important，决定保底与底线）----
  { field: 'risk_preference', layer: 5, label: '风险偏好', priority: 'important',
    question: '宁可去弱一点学校的好专业，还是好一点学校的普通专业？宁可热门城市普通平台，还是非热门城市更高平台？',
    options: ['弱校好专业', '好校普通专业', '热门城市普通平台', '非热门城市高平台', '不确定'] },
  { field: 'unacceptable', layer: 5, label: '不可接受项', priority: 'required',
    question: '哪些专业、地区、学校类型绝对不能接受？哪些情况一旦被调剂到就不能接受？' },
  { field: 'adjustment_tolerance', layer: 5, label: '调剂接受度', priority: 'important',
    question: '是否接受专业调剂？如果服从调剂，组内最差的专业能不能接受？' },

  // ---- 第 6 层：长期目标（important，决定方案主轴）----
  { field: 'long_term_path', layer: 6, label: '长期路径', priority: 'important',
    question: '四年后更想直接就业、继续升学（考研/保研）、考公考编，还是先保留选择？',
    options: ['直接就业', '升学跳板', '考公考编', '行业系统', '先探索'] },
  { field: 'target_city', layer: 6, label: '目标城市', priority: 'important',
    question: '想在哪个城市或区域长期发展？读书城市是否必须等于未来就业城市？' },
  { field: 'execution_willingness', layer: 6, label: '执行意愿', priority: 'important',
    question: '如果方案依赖升学跳板（保持排名、备考、联系导师），学生是否愿意投入三四年？' },

  // ---- 第 7 层：价值观（optional，公共服务路径判断）----
  { field: 'public_service', layer: 7, label: '公共服务意愿', priority: 'optional',
    question: '是否愿意考虑基层、偏远地区、公共服务或国家政策导向的路径？这是内心认可，还是家长期望？' },

  // ---- 第 8 层：宏观变量（optional，长期趋势）----
  { field: 'ai_willingness', layer: 8, label: 'AI/数据学习意愿', priority: 'optional',
    question: '是否愿意长期学习 AI 工具、数据分析等第二能力？更偏向哪类组合（数据/AI/语言/法律/产业知识）？' },

  // ---- 第 9 层：输出偏好（optional，交付形式）----
  { field: 'output_format', layer: 9, label: '输出偏好', priority: 'optional',
    question: '希望拿到什么形式的产出？',
    options: ['快速方向判断', '完整报告', '候选学校池', '冲稳保志愿表', '家长沟通版', '入学后计划'] },
]

/** 每层最多一次问几个问题（遵循"不一次性抛过多"原则） */
export const MAX_PER_CALL = 5
