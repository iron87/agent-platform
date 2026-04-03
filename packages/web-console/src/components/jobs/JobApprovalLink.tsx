interface JobApprovalLinkProps {
  pendingApprovalId: string | null;
  onOpenApproval: (approvalId: string) => void;
}

export function JobApprovalLink({ pendingApprovalId, onOpenApproval }: JobApprovalLinkProps) {
  if (!pendingApprovalId) {
    return null;
  }

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
      Pending approval: {pendingApprovalId}
      <button
        className="ml-2 rounded-md border border-amber-300 bg-white px-2 py-1 text-xs font-semibold"
        type="button"
        onClick={() => onOpenApproval(pendingApprovalId)}
      >
        Open
      </button>
    </div>
  );
}
