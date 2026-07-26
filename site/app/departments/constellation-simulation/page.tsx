export default function ConstellationSimulationPage() {
  return (
    <main className="placeholderPage">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brandMark">GY</span>
          <span><b>观宇芯算研发部周报</b><small>DEPARTMENT / 02</small></span>
        </a>
        <nav className="portalNav">
          <a href="/">总览</a>
          <a href="/departments/orbitinfer">星载推理引擎</a>
          <a href="/library">论文库</a>
        </nav>
        <div className="issueStatus"><span className="pulse mutedPulse" />范围待确认</div>
      </header>
      <section className="placeholderHero">
        <p className="kicker">DEPARTMENT SCOPE PLACEHOLDER</p>
        <h1>星座智算<br /><em>仿真平台</em></h1>
        <p>
          部门入口、路由和共享数据接口已经建立。当前不会复用“星载大模型推理引擎”的关键词和选稿，
          避免在缺少部门材料时生成不可靠内容。
        </p>
      </section>
      <section className="scopeChecklist">
        <div>
          <span>READY</span>
          <h2>已经准备</h2>
          <ul>
            <li>独立部门路由与周报入口</li>
            <li>共享论文、框架、数据集和公众号证据层</li>
            <li>独立评分、选稿和发布状态的数据结构</li>
          </ul>
        </div>
        <div>
          <span>REQUIRED</span>
          <h2>启动前需要</h2>
          <ul>
            <li>部门任务与项目资料</li>
            <li>核心方向和明确排除项</li>
            <li>固定顶会、期刊、机构和开源项目池</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
