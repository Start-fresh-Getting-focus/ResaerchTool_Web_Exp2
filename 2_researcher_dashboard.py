import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import io
import zipfile

# 固定构件目标（StepID -> 构件名 + 编号列表）
STEP_TARGETS = {
    1: ("2. Platform", ["2"]),
    2: ("11. Anti-Tip Assembly", ["11"]),
    3: ("9. 5 in.caster / 1. Lower Ladder", ["9", "1"]),
    4: ("3. Mounting Bracket", ["3"]),
    5: ("5. Brace", ["5"]),
    6: ("4. Piece Support / 12. Tightening Knob", ["4", "12"]),
    7: ("6. Shelf Brace", ["6"]),
    8: ("10. Locking Pin", ["10"]),
    9: ("8. Wire Grid Shelf -L- / 7. Wire Grid Shelf -S-", ["8", "7"])
}

# 步骤分组定义
GROUP_STEPS = {
    "A": [1, 2, 3],
    "B": [4, 5, 6],
    "C": [7, 8, 9]
}

# 修正后的拉丁方设计分配表（根据您提供的正确顺序）
LATIN_SQUARE = {
    1: {"A": "Static AR", "B": "Full CV", "C": "Step-Aware CV"},
    2: {"A": "Static AR", "B": "Full CV", "C": "Step-Aware CV"},
    3: {"A": "Static AR", "B": "Full CV", "C": "Step-Aware CV"},
    4: {"A": "Static AR", "B": "Full CV", "C": "Step-Aware CV"},
    5: {"A": "Full CV", "B": "Step-Aware CV", "C": "Static AR"},
    6: {"A": "Full CV", "B": "Step-Aware CV", "C": "Static AR"},
    7: {"A": "Full CV", "B": "Step-Aware CV", "C": "Static AR"},
    8: {"A": "Full CV", "B": "Step-Aware CV", "C": "Static AR"},
    9: {"A": "Step-Aware CV", "B": "Static AR", "C": "Full CV"},
    10: {"A": "Step-Aware CV", "B": "Static AR", "C": "Full CV"},
    11: {"A": "Step-Aware CV", "B": "Static AR", "C": "Full CV"},
    12: {"A": "Step-Aware CV", "B": "Static AR", "C": "Full CV"}
}

# 初始化 session 状态
if 'current_step' not in st.session_state:
    st.session_state.current_step = 1
    st.session_state.data = []
    st.session_state.show_questionnaire = False
    st.session_state.show_group_complete = False
    st.session_state.step_records = {}
    st.session_state.experiment_complete = False

def get_current_group(step):
    """获取当前步骤所属的组(A/B/C)"""
    for group, steps in GROUP_STEPS.items():
        if step in steps:
            return group
    return "Unknown"

def get_system_for_group(participant_id, group):
    """根据拉丁方设计获取指定组的系统"""
    participant_id = int(participant_id)
    if participant_id in LATIN_SQUARE:
        return LATIN_SQUARE[participant_id].get(group, "Unknown")
    return {"A": "Static AR", "B": "Full CV", "C": "Step-Aware CV"}[group]

def get_current_system(participant_id, step):
    """获取当前步骤的系统"""
    group = get_current_group(step)
    return get_system_for_group(participant_id, group)

def parse_likert(label):
    """解析Likert量表的选择"""
    return int(label[0]) if label and label[0].isdigit() else None

# 实验设置页面
def setup_page():
    st.header("实验配置")
    participant_id = st.number_input("受试者编号（请输入 1 - 12）", min_value=1, max_value=100, step=1)
    
    if participant_id > 12:
        st.warning("⚠️ 当前编号超出预设范围(1-12)，将使用默认系统顺序")
    
    # 显示系统分配
    if participant_id in LATIN_SQUARE:
        systems = LATIN_SQUARE[participant_id]
        st.success(f"✅ 系统分配：")
        st.markdown(f"- **步骤组 A (步骤 1-3):** {systems['A']}")
        st.markdown(f"- **步骤组 B (步骤 4-6):** {systems['B']}")
        st.markdown(f"- **步骤组 C (步骤 7-9):** {systems['C']}")
    else:
        st.success("✅ 系统顺序：Static AR → Full CV → Step-Aware CV")

    if st.button("开始实验"):
        st.session_state.participant_id = f"{participant_id:02d}"  # 编号格式为 '01', '02', etc.
        st.session_state.current_step = 1
        st.rerun()

# 记录步骤页面
def record_step():
    current_step = st.session_state.current_step
    participant_id = int(st.session_state.participant_id)
    current_system = get_current_system(participant_id, current_step)
    current_group = get_current_group(current_step)
    target_label, target_ids = STEP_TARGETS.get(current_step, ("N/A", []))
    
    st.header(f"步骤 {current_step}/9")
    st.subheader(f"当前系统: {current_system} | 步骤组: {current_group}")
    st.markdown(f"**🎯 目标构件：{target_label}**")
    
    # 初始化当前步骤的记录
    if current_step not in st.session_state.step_records:
        st.session_state.step_records[current_step] = {
            'start_time': None,
            'attempts': [],  # 存储每次尝试 {timestamp, answer, is_correct}
            'first_correct_time': None,
            'final_correct_time': None
        }
    
    record = st.session_state.step_records[current_step]
    
    # 步骤开始按钮
    if not record['start_time']:
        if st.button("▶️ 开始本步骤任务（点击后开始计时）"):
            record['start_time'] = datetime.now(pytz.timezone("America/Edmonton")).isoformat()
            st.rerun()
        st.stop()
    
    # 处理用户输入
    with st.form("step_form", clear_on_submit=True):
        answer = st.text_input("受试者回答编号或名称（多个用空格分隔）")
        note = st.text_area("📝 观察备注（可选）", placeholder="在此记录你观察到的行为、操作习惯、问题等...")
        
        submitted = st.form_submit_button("提交尝试")
        
        if submitted and answer:
            now = datetime.now(pytz.timezone("America/Edmonton"))
            timestamp = now.isoformat()
            
            # 检查答案是否正确
            answer_list = [s.strip() for s in answer.split() if s.strip()]
            is_correct = any(ans in target_ids for ans in answer_list)
            
            # 记录尝试
            attempt = {
                'timestamp': timestamp,
                'answer': answer,
                'is_correct': is_correct
            }
            record['attempts'].append(attempt)
            
            # 如果是首次正确
            if is_correct and not record['first_correct_time']:
                record['first_correct_time'] = timestamp
            
            # 如果是最终正确（用户确认）
            if is_correct:
                record['final_correct_time'] = timestamp
                st.success("✅ 回答正确！")
            else:
                st.error("❌ 回答错误，请继续尝试")
    
    # 显示当前状态
    start_time = datetime.fromisoformat(record['start_time'])
    elapsed = round((datetime.now(pytz.timezone("America/Edmonton")) - start_time).total_seconds(), 1)
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"🕒 本步骤已用时: {elapsed}秒")
        st.info(f"📊 尝试次数: {len(record['attempts'])}")
    
    with col2:
        if record['final_correct_time']:
            st.success(f"🏁 最终确认时间: {record['final_correct_time']}")
    
    # 完成步骤按钮（仅在用户有正确尝试时可用）
    if record['final_correct_time']:
        if st.button("✅ 完成本步骤"):
            # 计算首次是否命中
            first_attempt_correct = False
            if record['attempts']:
                first_attempt_correct = record['attempts'][0]['is_correct']
            
            # 计算总耗时
            final_correct_time = datetime.fromisoformat(record['final_correct_time'])
            total_duration = round((final_correct_time - start_time).total_seconds(), 2)
            
            # 计算错误次数
            error_count = sum(1 for a in record['attempts'] if not a['is_correct'])
            
            # 保存实验记录
            step_data = {
                "RecordType": "Experiment",
                "Participant": st.session_state.participant_id,
                "StepID": current_step,
                "StepGroup": current_group,
                "System": current_system,
                "TargetLabel": target_label,
                "StartTime": record['start_time'],
                "EndTime": record['final_correct_time'],
                "TotalDuration": total_duration,
                "AttemptCount": len(record['attempts']),
                "ErrorCount": error_count,
                "FirstAttemptCorrect": first_attempt_correct,  # 优化变量名
                "Note": note
            }
            
            st.session_state.data.append(step_data)
            
            # 检查是否完成当前步骤组
            if current_step in [3, 6, 9]:
                st.session_state.show_group_complete = True
            else:
                st.session_state.current_step += 1
            st.rerun()
    
    # 导航按钮
    col1, col2 = st.columns(2)
    if col1.button("⬅️ 返回上一步") and current_step > 1:
        st.session_state.current_step -= 1
        st.rerun()
    
    if col2.button("↩️ 重置本步骤"):
        st.session_state.step_records[current_step] = {
            'start_time': record['start_time'],  # 保留开始时间
            'attempts': [],
            'first_correct_time': None,
            'final_correct_time': None
        }
        st.rerun()

# 步骤组完成页面
def show_group_complete():
    current_step = st.session_state.current_step
    participant_id = int(st.session_state.participant_id)
    group = get_current_group(current_step)
    system = get_system_for_group(participant_id, group)
    
    st.header(f"✅ 步骤组 {group} 完成")
    st.subheader(f"系统: {system}")
    st.success(f"您已完成{system}系统的所有任务！")
    st.info("接下来请填写关于此系统的问卷")
    
    if st.button("➡️ 继续填写问卷"):
        st.session_state.show_group_complete = False
        st.session_state.show_questionnaire = True
        st.rerun()

# 问卷页面（优化后的界面）
def questionnaire():
    current_step = st.session_state.current_step
    participant_id = int(st.session_state.participant_id)
    group = get_current_group(current_step)
    system = get_system_for_group(participant_id, group)
    
    st.header(f"{system} System Questionnaire")
    with st.form("questionnaire_form"):

        likert_labels = ["1 (Strongly Disagree)", "2", "3", "4", "5", "6", "7 (Strongly Agree)"]
        
        # 创建更美观的问卷布局
        def question_block(question_key, english, chinese):
            st.markdown(f"**{question_key}**")
            st.markdown(f"<div style='margin-bottom: 8px;'>{english}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='margin-bottom: 16px;'>{chinese}</div>", unsafe_allow_html=True)
            return st.radio("", likert_labels, horizontal=True, index=None, key=question_key)
        
        # SART 问卷
        st.markdown("### 🧠 SART – Situation Awareness")
        st.markdown(f"""
        **System being evaluated: `{system}`**

        Please evaluate this system (the one you just used in the last round of tasks) based on your experience in completing the component search tasks.  
        Use a 7-point scale: 1 = Strongly disagree, 7 = Strongly agree.

        请根据您刚刚完成的构件查找任务，评价“该系统”（当前轮次所使用的系统）的表现。  
        每个问题请根据您的实际体验程度，选择 1 到 7 分（1 = 非常不同意，7 = 非常同意）。

        """)
        sart_questions = [
            ("SART_1", 
             "I received enough information to help me quickly identify the target component.", 
             "我获得了足够的信息来帮助我快速查找到目标构件。"),
            ("SART_2", 
             "The information provided by the system was clear and accurate.", 
             "系统提供的信息清晰、准确，有助于我识别正确的构件。"),
            ("SART_3", 
             "I clearly understood what was happening during the component search tasks.", 
             "我能清楚理解查找任务中的提示与状态信息。"),
            ("SART_4", 
             "The task environment and recognition process were complex.", 
             "任务环境和识别过程较为复杂。"),
            ("SART_5", 
             "The task environment and information changed unexpectedly or frequently during the task.", 
             "任务环境和出现的信息变化频繁或难以预料。"),
            ("SART_6", 
             "The system behavior or visual information was inconsistent or unpredictable during the task.", 
             "任务中系统行为或视觉提示不一致或不可预测。"),
            ("SART_7", 
             "I had to concentrate intensely to stay focused during the entire object search process.", 
             "我必须全程高度集中注意力，才能在整个构件查找过程中保持专注。"),
            ("SART_8", 
             "I still had enough mental resources left to process other environmental information during the task.", 
             "我还有足够的精力来注意其他环境信息。"),
            ("SART_9", 
             "I had to exert a lot of effort to understand the system's instructions and locate the correct component.", 
             "我必须付出很大努力才能理解系统提示并找到正确的构件。"),
            ("SART_10", 
             "I remained alert and attentive throughout the tasks.", 
             "我在任务中始终保持专注与警觉。")
        ]
        sart = {k: question_block(k, en, zh) for k, en, zh in sart_questions}
        
        # System Usability 问卷
        st.markdown("### 💻 System Usability & Experience")
        st.markdown(f"""
        **System being evaluated: `{system}`**

        Please evaluate this system (the one you just used in the last round of tasks) based on your experience in completing the component search tasks.  
        Use a 7-point scale: 1 = Strongly disagree, 7 = Strongly agree.

        请根据您刚刚完成的构件查找任务，评价“该系统”（当前轮次所使用的系统）的表现。  
        每个问题请根据您的实际体验程度，选择 1 到 7 分（1 = 非常不同意，7 = 非常同意）。
        
        """)

        su_questions = [
            ("SU_1", 
             "This system provided information that was highly relevant to my task.", 
             "该系统提供的信息与我当前的任务高度相关。"),
            ("SU_2", 
             "This system's prompts effectively guided me to the correct target.", 
             "该系统的提示成功引导我找到正确目标。"),
            ("SU_3", 
             "This system's visual prompts were excessive or distracting.", 
             "该系统的提示信息过多或让我感到分心。"),
            ("SU_4", 
             "The prompts were stable and consistent throughout this system.", 
             "该系统的提示表现稳定、一致，没有跳动或不连贯。"),
            ("SU_5", 
             "I trusted this system's information to be reliable and accurate.", 
             "我信任该系统提供的信息是可靠且准确的。"),
            ("SU_6", 
             "The system provided guidance at appropriate timing.", 
             "该系统在恰当的时间点提供了提示，有助于我及时完成任务。"),
            ("SU_7", 
             "The system's interface was visually clean and well-organized.", 
             "该系统界面整洁、信息排布合理，不混乱。"),
            ("SU_8", 
             "Overall, I am satisfied with using this system.", 
             "总体而言，我对该系统的使用体验感到满意。")
        ]
        su = {k: question_block(k, en, zh) for k, en, zh in su_questions}
        
        # NASA-TLX 问卷
        st.markdown("### ⚙️ NASA-TLX - Task Load Index")
        
        st.markdown(f"""
        **System being evaluated: `{system}`**

        Please evaluate this system (the one you just used in the last round of tasks) based on your experience in completing the component search tasks.  
        Use a 7-point scale: 1 = Strongly disagree, 7 = Strongly agree.

        请根据您刚刚完成的构件查找任务，评价“该系统”（当前轮次所使用的系统）的表现。  
        每个问题请根据您的实际体验程度，选择 1 到 7 分（1 = 非常不同意，7 = 非常同意）。
        
        """)

        tlx_questions = [
            ("TLX_1", 
             "How mentally demanding was the task?", 
             "这个任务在心理/思维上对你有多大挑战？"),
            ("TLX_2", 
             "How physically demanding was the task?", 
             "这个任务在体力上对你有多大挑战？"),
            ("TLX_3", 
             "How hurried or rushed was the pace of the task?", 
             "这个任务的节奏是否让你感觉匆忙或赶时间？"),
            ("TLX_4", 
             "How successful were you in accomplishing what you were asked to do?", 
             "你认为自己完成任务的成功程度如何？"),
            ("TLX_5", 
             "How hard did you have to work to accomplish your level of performance?", 
             "为了达到目前的任务表现，你付出了多大努力？"),
            ("TLX_6", 
             "How insecure, discouraged, irritated, stressed, and annoyed were you?", 
             "你在任务中感到多少不安、沮丧、焦虑、烦躁？")
        ]
        tlx = {k: question_block(k, en, zh) for k, en, zh in tlx_questions}
        
        col1, col2 = st.columns([1, 1])
        back = col1.form_submit_button("⬅️ 返回上一步")
        submit = col2.form_submit_button("✅ 提交问卷并继续")
        
        if back:
            st.session_state.show_questionnaire = False
            st.session_state.show_group_complete = True
            st.rerun()
        
        if submit:
            # 验证问卷完整性
            missing = [k for k, v in {**sart, **su, **tlx}.items() if v is None]
            if missing:
                st.error(f"⚠️ 请完整填写所有问题再提交！缺失项: {len(missing)}")
                st.stop()
            
            # 创建问卷记录
            result = {
                "RecordType": "Questionnaire",
                "Participant": st.session_state.participant_id,
                "System": system,
                "StepGroup": group
            }
            
            # 添加问卷答案
            result.update({k: parse_likert(v) for k, v in sart.items()})
            result.update({k: parse_likert(v) for k, v in su.items()})
            result.update({k: parse_likert(v) for k, v in tlx.items()})
            
            st.session_state.data.append(result)
            st.session_state.show_questionnaire = False
            st.session_state.current_step += 1
            
            # 检查实验是否完成
            if st.session_state.current_step > 9:
                st.session_state.experiment_complete = True
            st.rerun()

# 主控制流
if 'participant_id' not in st.session_state:
    setup_page()
elif st.session_state.experiment_complete:
    st.balloons()
    st.success("✅ 实验完成！Experiment Complete!")
    
    # 分离实验数据和问卷数据
    experiment_data = [r for r in st.session_state.data if r.get("RecordType") == "Experiment"]
    questionnaire_data = [r for r in st.session_state.data if r.get("RecordType") == "Questionnaire"]
    
    # 创建数据框
    experiment_df = pd.DataFrame(experiment_data)
    questionnaire_df = pd.DataFrame(questionnaire_data)
    
    # 创建内存中的 zip 文件
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # 添加实验数据 CSV
        if not experiment_df.empty:
            # 选择实验数据需要的列
            experiment_cols = [
                "Participant", "StepID", "StepGroup", "System", "TargetLabel",
                "StartTime", "EndTime", "TotalDuration", "AttemptCount",
                "ErrorCount", "FirstAttemptCorrect", "Note"
            ]
            experiment_clean = experiment_df[experiment_cols]
            zip_file.writestr("experiment_data.csv", experiment_clean.to_csv(index=False))
        
        # 添加问卷数据 CSV
        if not questionnaire_df.empty:
            # 选择问卷数据需要的列
            questionnaire_cols = ["Participant", "System", "StepGroup"]
            questionnaire_cols += [col for col in questionnaire_df.columns if col.startswith("SART_")]
            questionnaire_cols += [col for col in questionnaire_df.columns if col.startswith("SU_")]
            questionnaire_cols += [col for col in questionnaire_df.columns if col.startswith("TLX_")]
            
            questionnaire_clean = questionnaire_df[questionnaire_cols]
            zip_file.writestr("questionnaire_data.csv", questionnaire_clean.to_csv(index=False))
    
    # 准备下载按钮
    st.markdown("### 📦 下载实验数据")
    st.download_button(
        label="📥 下载数据包 (ZIP)",
        data=zip_buffer.getvalue(),
        file_name=f"experiment_data_{st.session_state.participant_id}.zip",
        mime="application/zip"
    )
    
    # 显示数据预览
    st.subheader("实验数据预览")
    st.dataframe(experiment_df.head())
    
    st.subheader("问卷数据预览")
    st.dataframe(questionnaire_df.head())
    
    if st.button("🔄 开始新实验"):
        st.session_state.clear()
        st.rerun()
elif getattr(st.session_state, 'show_group_complete', False):
    show_group_complete()
elif getattr(st.session_state, 'show_questionnaire', False):
    questionnaire()
elif st.session_state.current_step <= 9:
    record_step()