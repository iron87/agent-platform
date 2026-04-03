interface JsonViewerProps {
  data: unknown;
}

export function JsonViewer({ data }: JsonViewerProps) {
  return (
    <pre className="max-h-[28rem] overflow-auto rounded-xl border border-teal-100 bg-[#f9fffe] p-3 text-xs leading-5 text-teal-950">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
