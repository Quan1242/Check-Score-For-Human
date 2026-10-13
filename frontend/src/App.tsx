import GuidedWorkflow from './features/GuidedWorkflow';

export default function App() {
  return <div className="layout">
    <aside>
      <div className="brand">M49<span>ANNOTATION BENCHMARK</span></div>
      <p className="muted">Chọn tác vụ muốn test và bắt đầu thử nghiệm.</p>
      <p className="muted">AI chạy trên Colab.<br/>Tự nhận kết quả qua Google Drive.</p>
    </aside>
    <main><GuidedWorkflow/></main>
  </div>;
}
