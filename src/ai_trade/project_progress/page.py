"""Read-only Streamlit page; imports neither market adapters nor SQLite."""
import streamlit as st

from .core import METRICS, PlanError, calculate, dependency_failures, load, snapshots


def render():
    st.title("项目进度 · A股量化系统 V1.3")
    st.caption("离线管理看板 · 只读正式 TASK_METRICS.json · 不采集行情、不创建数据库、不改任务状态")
    try:
        data = load()
        result, current = calculate(data), snapshots(data)
    except (PlanError, OSError) as exc:
        st.error(f"任务数据无效，未显示伪造的完成率：{exc}")
        st.stop()
    st.metric("有证据的加权完成率", f"{result['project_percent']:.4f}%")
    st.info("这是首版规划权重下的验收进度，不是生产就绪率。无证据计零，失败计零；历史诊断零权重，避免重复计数。")
    st.write("数据截止：", data['updated_at'], "；依据 main：", data['baseline'], "；计划版本：", data['plan_version'])
    st.caption("阶段权重 × 阶段内任务权重 × 通过验收点权重；代码、测试、独立审查、合并和生产准入分列。")
    nxt = result['next']
    if nxt:
        st.success(f"推荐下一项：{nxt['id']} · {nxt['title']}")
        st.write(nxt['reason'])
        if nxt['origin'] == 'SUGGESTION':
            st.warning("仅建议立项，尚未创建或执行；建议本身不会改变任务状态。")
    else:
        st.warning("没有前置条件满足的候选任务；先人工处理阻塞。")
    st.subheader("阶段进度")
    for s in data['stages']:
        value = result['stage_percent'][s['id']]
        st.progress(value/100, text=f"{s['id']} {s['name']} · 权重 {s['weight']}% · 已证实 {value:g}%")
    st.subheader("TASK 状态分布")
    st.bar_chart(result['state_counts'], use_container_width=True)
    options = [t['id'] for t in data['tasks']]
    selected = st.selectbox("任务详情", options)
    task = next(t for t in data['tasks'] if t['id'] == selected)
    event = current[selected]
    st.write(task['title'], " · ", event['state'], " · ", task['origin'])
    st.write("目标：", task['goal'])
    st.write("唯一指定模型：", task['assigned_model'], task['assigned_effort'],
             "；分配依据：", task['model_assignment'], "；历史实际模型：", task['actual_model'] or '未知')
    st.caption(task['model_basis'])
    st.write("估计工时：", task['estimated_hours'] or '未知', "；实际小时：", event['actual_hours'] if event['actual_hours'] is not None else '未知')
    st.write("独立审查：", event['review']['status'], "；生产准入：", event['production']['status'])
    st.write("PR（独立记录）：", event['prs'] or '无 / 尚未创建')
    st.dataframe([{"验收点":a['label'],"权重":a['weight'],"强制":a['mandatory'],
                   "结果":event['results'][a['id']]['status'],
                   "证据":', '.join(event['results'][a['id']]['evidence']) or '无'} for a in task['acceptance']],
                 hide_index=True, use_container_width=True)
    st.write("最近更新依据：", event['at'], event['reason'], "；证据 ID：", event['basis'])
    missing = dependency_failures(task, current)
    if missing:
        st.warning("当前前置条件缺口（不篡改旧验收记录）："+'；'.join(missing))
    st.subheader("当前阻塞与未满足依赖")
    if not result['blockers']:
        st.info("没有已记录阻塞；未验证验收点仍不能视为通过。")
    for item in result['blockers']:
        st.write(item['id'], '；'.join(item['reasons']+item['dependencies']))
    with st.expander("计算口径、更新方法与证据边界"):
        st.write(data['weight_basis'])
        st.code("python -m ai_trade.project_progress --check-docs\npython -m ai_trade.project_progress --simulate TASK-002 offline FAIL")
        st.write("人工反馈 → --propose 生成新候选 → 审查独立 PR → --render；正式状态不会由页面、测试或 GitHub 自动更新。")
        st.write("低风险边界明确任务可提议 Agnes 3.0 Flash；时点、Schema、未来函数及独立审查指定 GPT-6.1 Sol / High。提议型号不证明已可用；历史未知型号不补造。")
        st.caption(str(METRICS))
