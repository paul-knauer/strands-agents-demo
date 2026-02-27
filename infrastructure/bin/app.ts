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

// The MODEL_ARN is the full Bedrock foundation model ARN scoped into the
// BedrockInvoke IAM policy.  In CI the pipeline sets this via the environment.
// The fallback value is the pinned Claude 3.7 Sonnet model used by this
// project so that local `cdk synth` runs still produce a valid template.
const modelArn =
  process.env.MODEL_ARN ??
  'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-7-sonnet-20250219-v1:0';

// ---------------------------------------------------------------------------
// Staging stack
// ---------------------------------------------------------------------------
new AgentStack(app, 'AgentStack/Staging', {
  env,
  environment: 'staging',
  imageTag,
  modelArn,
  description: 'nCino Banking Agent — AgentCore supporting infrastructure (staging)',
});

// ---------------------------------------------------------------------------
// Production stack
// ---------------------------------------------------------------------------
new AgentStack(app, 'AgentStack/Production', {
  env,
  environment: 'production',
  imageTag,
  modelArn,
  description: 'nCino Banking Agent — AgentCore supporting infrastructure (production)',
});

app.synth();
