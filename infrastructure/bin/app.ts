#!/usr/bin/env node
/**
 * CDK Application entry point.
 *
 * Instantiates two AgentStack instances — one for staging and one for
 * production — using the stack IDs that the GitHub Actions workflow expects:
 *
 *   AgentStack/Staging
 *   AgentStack/Production
 *
 * The IMAGE_TAG environment variable carries the immutable ECR image tag
 * (git SHA) injected by the pipeline. It defaults to "latest" only for
 * local synth runs where no tag has been set.
 */

import * as cdk from 'aws-cdk-lib';
import { AgentStack } from '../lib/agent-stack';

const app = new cdk.App();

const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? 'us-east-1',
};

// The IMAGE_TAG is the immutable git SHA injected by the pipeline.
// Locally it falls back to "latest" so `cdk synth` still runs cleanly.
const imageTag = process.env.IMAGE_TAG ?? 'latest';

// ---------------------------------------------------------------------------
// Staging stack
// ---------------------------------------------------------------------------
new AgentStack(app, 'AgentStack/Staging', {
  env,
  environment: 'staging',
  imageTag,
  description: 'nCino Banking Agent — AgentCore supporting infrastructure (staging)',
});

// ---------------------------------------------------------------------------
// Production stack
// ---------------------------------------------------------------------------
new AgentStack(app, 'AgentStack/Production', {
  env,
  environment: 'production',
  imageTag,
  description: 'nCino Banking Agent — AgentCore supporting infrastructure (production)',
});

app.synth();
