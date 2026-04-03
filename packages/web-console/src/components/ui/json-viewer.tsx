interface JsonViewerProps {
  data: unknown;
}

export function JsonViewer({ data }: JsonViewerProps) {
  return (
    <pre className="max-h-[28rem] overflow-auto rounded-md border bg-white p-3 text-xs leading-5 text-slate-900">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
