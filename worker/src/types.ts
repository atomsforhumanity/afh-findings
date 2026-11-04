// The shapes the Python publisher writes. Keep in sync with src/afh_findings/registry.py
// (index.json) and src/afh_findings/manifest.py (finding.json).

export interface Env {
  FINDINGS: R2Bucket;
  SITE_URL: string;
  FEEDBACK_URL?: string;
}

export interface Author {
  name: string;
  orcid?: string;
  affiliation?: string;
}

export interface Change {
  type: string;
  summary: string;
}

export interface VersionEntry {
  version: number;
  published: string;
  change: Change | null;
  entry: string;
  status: string;
  publisher?: string | null;
}

export interface FindingEntry {
  id: string;
  title: string;
  claim: string;
  authors: Author[];
  project: string;
  kind: string;
  status: string;
  keywords: string[];
  builds_on: string[];
  supersedes: string | null;
  formerly?: string[];
  license: Record<string, string> | null;
  private_code: string[];
  state: "active" | "retracted" | "withdrawn";
  state_reason: string | null;
  state_date: string | null;
  superseded_by: string | null;
  doi: string | null;
  stacks_url: string | null;
  versions: VersionEntry[];
  latest: number;
  first_published: string;
  updated: string;
  events: Array<Record<string, unknown>>;
}

export interface Index {
  schema: string;
  updated: string | null;
  findings: Record<string, FindingEntry>;
}

export interface FileRecord {
  path: string;
  sha256: string;
  size: number;
}

export interface Material {
  path: string;
  description?: string;
}

export interface Upstream {
  name: string;
  doi?: string;
  url?: string;
  license?: string;
  note?: string;
}

export interface Manifest {
  id: string;
  version: number;
  published: string;
  publisher: string | null;
  title: string;
  claim: string;
  authors: Author[];
  project: string;
  kind: string;
  status: string;
  keywords: string[];
  scope: { not_tested: string[]; [key: string]: unknown };
  data: Material[];
  data_none: string | null;
  code: Material[];
  code_none: string | null;
  private_code: string[];
  upstream: Upstream[];
  builds_on: string[];
  supersedes: string | null;
  formerly?: string[];
  entry: string;
  check: string | null;
  license: Record<string, string>;
  change: Change | null;
  profiles: Record<string, string>;
  files: FileRecord[];
}
