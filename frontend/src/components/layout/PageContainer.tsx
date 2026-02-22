export default function PageContainer({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">{title}</h1>
      {children}
    </div>
  );
}
