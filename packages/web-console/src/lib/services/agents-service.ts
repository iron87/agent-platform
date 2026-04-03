import { apiRequest } from "../api-client";
import type { AgentCreateInput, AgentSummary, ConsoleProfile } from "../types";

export async function listAgents(profile: ConsoleProfile): Promise<AgentSummary[]> {
  const response = await apiRequest<any>({
    profile,
    path: "/agents",
    method: "GET",
  });

  const items = Array.isArray(response) ? response : response?.agents ?? response?.items ?? [];
  return items.map((item: any) => ({
    agentId: item.id ?? item.agentId ?? "",
    name: item.name ?? "unnamed-agent",
    description: item.description,
    createdAt: item.created_at ?? item.createdAt,
    graphType: item.graph_type,
    modelAlias: item.model_alias,
    version: item.version,
    semanticMemoryEnabled: item.semantic_memory_enabled,
    tools: item.tools ?? [],
    hitlTools: item.hitl_tools ?? [],
  }));
}

export async function createAgent(profile: ConsoleProfile, input: AgentCreateInput): Promise<AgentSummary> {
  const payload = await apiRequest<any>({
    profile,
    path: "/agents",
    method: "POST",
    body: JSON.stringify({
      name: input.name,
      prompt_file: input.promptFile?.trim() || undefined,
      prompt_text: input.promptText?.trim() || undefined,
      graph_type: input.graphType || "conversational",
      tools: input.tools ?? [],
      hitl_tools: input.hitlTools ?? [],
      model_alias: input.modelAlias || "default",
      max_execution_seconds: input.maxExecutionSeconds ?? 60,
      semantic_memory_enabled: input.semanticMemoryEnabled ?? false,
    }),
  });

  const created = payload?.agent ?? payload;

  return {
    agentId: created?.id ?? created?.agentId ?? "",
    name: created?.name ?? input.name,
    description: created?.description,
    createdAt: created?.created_at ?? created?.createdAt,
    graphType: created?.graph_type,
    modelAlias: created?.model_alias,
    version: created?.version,
    semanticMemoryEnabled: created?.semantic_memory_enabled,
    tools: created?.tools ?? [],
    hitlTools: created?.hitl_tools ?? [],
  };
}
