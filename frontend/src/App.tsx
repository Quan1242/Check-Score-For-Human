import GuidedWorkflow from './features/GuidedWorkflow';

export default function App() {
  return <div className="layout">
    <aside>
      <div className="brand"><div className="brand-symbol" aria-hidden="true">M<span>49</span></div>M49<span>ANNOTATION STUDIO</span></div>
      <div className="sidebar-intro"><span className="sidebar-label">KHÔNG GIAN THỬ NGHIỆM</span><h2>Từ nhãn đúng.<br/>Đến góc nhìn rõ.</h2><p>Khám phá sự khác biệt giữa người và AI trên cùng một bộ dữ liệu.</p></div>
      <div className="sidebar-orbit" aria-hidden="true"><i/><i/><div>Người<span>×</span>AI</div></div>
      <div className="sidebar-footer"><span className="sidebar-label">QUY TRÌNH M49</span><p>Gán nhãn → Đối chiếu → Đánh giá</p><small>AI chạy trên Colab<br/>Kết quả đồng bộ qua Google Drive</small></div>
    </aside>
    <main><GuidedWorkflow/></main>
  </div>;
}
