"use client";

import sourceData from "../source-data.json";

const healthNames: Record<string, string> = {
  ok: "采集正常",
  no_recent_update: "本期无更新",
  empty_feed: "Feed 暂为空",
  auth_failed: "授权失效",
  rate_limited: "上游限流",
  not_checked: "尚未检查",
};

function readableDate(value: string | null) {
  if (!value) return "尚未检查";
  return new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(new Date(value));
}

export default function SourcesPage() {
  return (
    <main className="sourcesPage">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brandMark">WX</span>
          <span><b>公众号固定订阅池</b><small>WECHAT SOURCE RADAR</small></span>
        </a>
        <nav className="portalNav">
          <a href="/">总览</a>
          <a href="/departments/orbitinfer">部门周报</a>
          <a href="/library">论文库</a>
        </nav>
        <div className="issueStatus"><span className="pulse" />{sourceData.accounts.length} 个固定来源</div>
      </header>

      <section className="sourcesHero">
        <p className="kicker">DISCOVERY · INTERPRETATION · VERIFICATION</p>
        <h1>公众号负责发现和解释<br /><em>原始来源负责证明</em></h1>
        <p>公众号文章不会冒充论文主记录；事实需要回到论文、顶会官网、GitHub 或官方项目页核验。</p>
      </section>

      <section className="sourceGrid">
        {sourceData.accounts.map((account, index) => (
          <article className="sourceCard" key={account.sourceId}>
            <div className="sourceHeader">
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h2>{account.name}</h2>
                <p>{account.tier === "S_Core" ? "核心订阅" : "活跃观察"} · {account.accountAlias}</p>
              </div>
              <b className={`health health-${account.health}`}>{healthNames[account.health] ?? account.health}</b>
            </div>
            <div className="sourceStats">
              <span>最近检查 {readableDate(account.checkedAt)}</span>
              <span>窗口内 {account.inWindow} 篇</span>
              <span>Feed {account.feedEntries} 条</span>
            </div>
            <div className="articleList">
              {account.articles.length ? account.articles.slice(0, 4).map((article) => (
                <a href={article.url ?? "#"} target="_blank" rel="noreferrer" key={article.url}>
                  <span>{readableDate(article.publishedAt)}</span>
                  <strong>{article.title}</strong>
                  <i>↗</i>
                </a>
              )) : <p className="noArticles">本地证据库暂未保存该账号文章。</p>}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
