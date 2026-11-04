declare namespace Cloudflare {
  interface Env {
    FINDINGS: R2Bucket;
    SITE_URL: string;
    FEEDBACK_URL?: string;
  }
}
