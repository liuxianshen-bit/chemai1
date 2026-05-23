-- =============================================
-- ChemAI 演示考试数据
-- 用法: sqlite3 chemai.db < data/demo_exam_data.sql
-- =============================================

-- 考试记录（高一1班）
INSERT OR IGNORE INTO exam_records (record_id, class_id, type, name, question_stats, avg_score, total_students, present_students, source, exam_date, generated_at, created_at)
VALUES ('demo_exam_001', 'class_2025_1', 'exam', '高一(1)班 第一次月考 - 化学', '{}', 0, 34, 34, 'ai_generated', '2026-03-15 08:00:00', '2026-03-12 08:00:00', '2026-03-12 08:00:00');

-- 考试记录（高一2班）
INSERT OR IGNORE INTO exam_records (record_id, class_id, type, name, question_stats, avg_score, total_students, present_students, source, exam_date, generated_at, created_at)
VALUES ('demo_exam_002', 'class_2025_2', 'exam', '高一(2)班 第一次月考 - 化学', '{}', 0, 33, 33, 'ai_generated', '2026-03-15 08:00:00', '2026-03-12 08:00:00', '2026-03-12 08:00:00');

-- 题目数据
INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_001', 'demo_exam_001', '下列物质的水溶液呈碱性的是（  ）',
 '["A. Na₂SO₄", "B. NH₄Cl", "C. NaHCO₃", "D. KNO₃"]',
 'C',
 'NaHCO₃为强碱弱酸盐，HCO₃⁻水解使溶液呈碱性。Na₂SO₄中性，NH₄Cl酸性，KNO₃中性。',
 '["盐类水解", "电解质溶液"]', 'easy', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_002', 'demo_exam_001', '下列反应中，水作氧化剂的是（  ）',
 '["A. 2Na + 2H₂O → 2NaOH + H₂↑", "B. 2F₂ + 2H₂O → 4HF + O₂", "C. Cl₂ + H₂O → HCl + HClO", "D. SO₂ + H₂O → H₂SO₃"]',
 'A',
 'A中水中的H⁺被还原为H₂，水作氧化剂。B中水中的O被氧化，水作还原剂。C、D为非氧化还原反应。',
 '["氧化还原反应", "氧化剂与还原剂"]', 'medium', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_003', 'demo_exam_001', '关于原电池的叙述正确的是（  ）',
 '["A. 原电池将电能转化为化学能", "B. 原电池负极发生还原反应", "C. 原电池正极发生氧化反应", "D. 原电池中电子从负极经外电路流向正极"]',
 'D',
 '原电池将化学能转化为电能（A错）；负极发生氧化反应（B错）；正极发生还原反应（C错）。电子从负极经外电路流向正极（D正确）。',
 '["原电池", "电化学基础"]', 'easy', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_004', 'demo_exam_001', '已知反应 N₂(g) + 3H₂(g) ⇌ 2NH₃(g) ΔH < 0，下列措施能提高N₂转化率的是（  ）',
 '["A. 升温", "B. 增大压强", "C. 使用催化剂", "D. 增加N₂浓度"]',
 'B',
 '该反应放热且气体分子数减少。升温平衡左移（A错）；增大压强平衡右移，N₂转化率提高（B对）；催化剂不改变平衡（C错）；增加N₂浓度使自身转化率降低（D错）。',
 '["化学平衡", "勒夏特列原理"]', 'medium', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_005', 'demo_exam_001', '室温下，0.1 mol/L 的 CH₃COOH 溶液中，下列关系正确的是（  ）',
 '["A. c(H⁺) = 0.1 mol/L", "B. c(CH₃COO⁻) = 0.1 mol/L", "C. c(H⁺) < c(CH₃COO⁻)", "D. c(H⁺) > c(OH⁻)"]',
 'D',
 'CH₃COOH为弱酸，部分电离，c(H⁺) < 0.1 mol/L（A错）；c(CH₃COO⁻) < 0.1 mol/L（B错）；c(H⁺) = c(CH₃COO⁻) + c(OH⁻) > c(CH₃COO⁻)（C错）；溶液显酸性，c(H⁺) > c(OH⁻)（D对）。',
 '["电解质溶液", "弱电解质的电离"]', 'medium', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_006', 'demo_exam_001', '下列化学反应速率的影响因素中，能显著提高反应速率的是（  ）',
 '["A. 降低温度", "B. 减小反应物浓度", "C. 使用合适的催化剂", "D. 减少反应物接触面积"]',
 'C',
 '催化剂能降低活化能，显著提高反应速率。降低温度（A错）、减小浓度（B错）、减少接触面积（D错）均降低反应速率。',
 '["化学反应速率", "催化剂"]', 'easy', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_007', 'demo_exam_001', '下列有机物的命名正确的是（  ）',
 '["A. 2-乙基丙烷", "B. 3-甲基丁烷", "C. 2-甲基戊烷", "D. 2-乙基-2-甲基丙烷"]',
 'C',
 'A正确名为2-甲基丁烷（最长链为4个碳）；B正确名为2-甲基丁烷（编号从离支链近端开始）；C正确（2-甲基戊烷）；D正确名为2,2-二甲基丁烷。',
 '["有机化学基础", "有机物的命名"]', 'medium', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_008', 'demo_exam_001', '下列各组物质中，化学键类型相同的是（  ）',
 '["A. HCl 和 NaCl", "B. H₂O 和 CO₂", "C. MgCl₂ 和 Na₂O", "D. NH₄Cl 和 KCl"]',
 'B',
 'A中HCl为共价键，NaCl为离子键；B中H₂O和CO₂均为共价键；C中MgCl₂为离子键，Na₂O为离子键，但MgCl₂含共价键；D中NH₄Cl含离子键和共价键，KCl仅含离子键。',
 '["物质结构", "化学键类型"]', 'hard', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_009', 'demo_exam_001', '常温下，将pH=3的盐酸与pH=11的氨水等体积混合后，溶液的pH（  ）',
 '["A. 等于7", "B. 小于7", "C. 大于7", "D. 无法判断"]',
 'C',
 '盐酸为强酸完全电离，c(H⁺)=10⁻³；氨水为弱碱部分电离，c(OH⁻)=10⁻³但氨水实际浓度远大于10⁻³。等体积混合后氨水过量，溶液显碱性，pH>7。',
 '["电解质溶液", "酸碱中和", "弱电解质的电离"]', 'hard', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_010', 'demo_exam_001', '某温度下，反应 2SO₂(g) + O₂(g) ⇌ 2SO₃(g) 的平衡常数 K=100。若起始浓度 c(SO₂)=0.2 mol/L，c(O₂)=0.1 mol/L，则平衡时 SO₂的转化率约为（  ）',
 '["A. 50%", "B. 67%", "C. 80%", "D. 95%"]',
 'B',
 '设转化了x mol/L的SO₂，则平衡时c(SO₂)=0.2-2x，c(O₂)=0.1-x，c(SO₃)=2x。K=(2x)²/[(0.2-2x)²(0.1-x)]=100。解得x≈0.067，转化率=2×0.067/0.2≈67%。',
 '["化学平衡", "平衡常数计算"]', 'hard', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_011', 'demo_exam_001', '用惰性电极电解 CuSO₄ 溶液，下列说法不正确的是（  ）',
 '["A. 阴极析出Cu", "B. 阳极产生O₂", "C. 溶液pH降低", "D. 溶液中c(Cu²⁺)增大"]',
 'D',
 '电解CuSO₄溶液：阴极Cu²⁺+2e⁻→Cu（A对）；阳极2H₂O-4e⁻→O₂↑+4H⁺（B对）；产生H⁺使pH降低（C对）；c(Cu²⁺)逐渐减小（D错）。',
 '["电解原理", "电化学基础"]', 'medium', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_012', 'demo_exam_001', '下列关于Na₂O₂的说法正确的是（  ）',
 '["A. Na₂O₂是白色固体", "B. Na₂O₂与水反应生成NaOH和O₂", "C. Na₂O₂中O的化合价为-2", "D. Na₂O₂属于碱性氧化物"]',
 'B',
 'Na₂O₂是淡黄色固体（A错）；与水反应2Na₂O₂+2H₂O→4NaOH+O₂↑（B对）；O的化合价为-1（C错）；Na₂O₂为过氧化物，不是碱性氧化物（D错）。',
 '["钠及其化合物", "过氧化钠"]', 'easy', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_013', 'demo_exam_001', '某溶液中可能含有 K⁺、NH₄⁺、Ba²⁺、SO₄²⁻、I⁻、CO₃²⁻。分别取样：①加足量氯水无现象；②加Ba(OH)₂溶液产生白色沉淀，继续加沉淀部分溶解。则一定存在的离子是（  ）',
 '["A. K⁺、CO₃²⁻", "B. NH₄⁺、SO₄²⁻", "C. K⁺、I⁻", "D. NH₄⁺、CO₃²⁻"]',
 'D',
 '①加氯水无现象说明无I⁻（I₂有颜色）；②加Ba(OH)₂产生白色沉淀且部分溶解，说明有CO₃²⁻（BaCO₃溶于酸）和SO₄²⁻（BaSO₄不溶）。有CO₃²⁻则无Ba²⁺。电中性需阳离子，有NH₄⁺（与OH⁻反应）。所以一定有NH₄⁺和CO₃²⁻。',
 '["离子检验", "离子共存"]', 'hard', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_014', 'demo_exam_001', '铝热反应：2Al + Fe₂O₃ → 2Fe + Al₂O₃，下列说法正确的是（  ）',
 '["A. Al被还原", "B. Fe₂O₃是还原剂", "C. 该反应放出大量热", "D. 该反应可用于工业炼铁"]',
 'C',
 'Al化合价升高被氧化（A错）；Fe₂O₃中Fe³⁺被还原，是氧化剂（B错）；铝热反应放出大量热用于焊接铁轨（C对）；工业炼铁用CO还原铁矿石（D错）。',
 '["氧化还原反应", "金属的冶炼"]', 'easy', 'ai_generated', 'passed', 1, 1, 1, 1);

INSERT OR IGNORE INTO questions (question_id, record_id, content, options, answer, analysis, knowledge_points, difficulty, source, audit_status, coefficient_correct, condition_correct, product_correct, structure_correct) VALUES
('demo_q_015', 'demo_exam_001', '下列实验操作能达到实验目的的是（  ）',
 '["A. 用pH试纸测量氯水的pH", "B. 用分液漏斗分离乙醇和水的混合物", "C. 用加热法除去NaHCO₃固体中的Na₂CO₃", "D. 用焰色反应检验溶液中的Na⁺"]',
 'D',
 '氯水有漂白性会使pH试纸褪色（A错）；乙醇与水互溶不能用分液（B错）；NaHCO₃加热分解为Na₂CO₃，不能除杂（C错）；焰色反应可检验Na⁺（黄色）（D对）。',
 '["化学实验", "物质检验与分离"]', 'medium', 'ai_generated', 'passed', 1, 1, 1, 1);

-- 障碍诊断配置（海老师 + 刘老师）
INSERT OR IGNORE INTO barrier_configs (config_id, teacher_id, concept_threshold, reading_threshold, expression_threshold, mastery_threshold, auto_sync_to_student)
VALUES ('bc_teacher_hai', 'teacher_hai', 3, 2, 3, 3, 1);

INSERT OR IGNORE INTO barrier_configs (config_id, teacher_id, concept_threshold, reading_threshold, expression_threshold, mastery_threshold, auto_sync_to_student)
VALUES ('bc_teacher_liu', 'teacher_liu', 3, 2, 3, 3, 1);
