/**
 * AgentStack — Supporting infrastructure for the nCino Banking Agent on AgentCore.
 *
 * This stack intentionally does NOT create AgentCore runtime resources
 * directly (the L1 constructs may not be available in every CDK version).
 * Instead it creates all of the durable supporting resources that AgentCore
 * needs at runtime:
 *
 *   - ECR repository       (image storage with scan-on-push)
 *   - IAM execution role   (least-privilege; assumed by AgentCore service principal)
 *   - CloudWatch log group (90-day retention)
 *   - CloudWatch alarm     (error-rate gate with SNS notification)
 *
 * CfnOutputs expose the key ARNs/names that downstream automation and the
 * AgentCore runtime configuration step consume.
 */

import * as cdk from 'aws-cdk-lib';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

// ---------------------------------------------------------------------------
// Stack props
// ---------------------------------------------------------------------------

export interface AgentStackProps extends cdk.StackProps {
  /** Deployment environment name — used in resource names and tags. */
  readonly environment: string;
  /**
   * Immutable image tag (git SHA) injected by the pipeline.
   * Stored as a CloudFormation parameter output so it is visible in the
   * console and traceable in deployment history.
   */
  readonly imageTag: string;
  /**
   * Full Bedrock foundation model ARN that the agent is permitted to invoke.
   * Scoped directly into the BedrockInvoke IAM policy statement so that the
   * execution role cannot call any other model.
   *
   * Example:
   *   arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-7-sonnet-20250219-v1:0
   *
   * Injected from the MODEL_ARN environment variable by app.ts; falls back to
   * a concrete default only for local `cdk synth` runs where no ARN is set.
   */
  readonly modelArn: string;
  /**
   * AgentCore runtime ID assigned when the runtime is first created.
   * Written to SSM so that rollback automation and the operations runbook can
   * discover it without consulting the console.
   *
   * Optional — when omitted (e.g. on initial deploy before the runtime exists)
   * the SSM parameter is written with the placeholder value "PENDING".
   */
  readonly agentRuntimeId?: string;
  /**
   * AgentCore alias ID assigned when the alias is first created.
   * Written to SSM alongside the runtime ID.
   *
   * Optional — same lifecycle caveat as agentRuntimeId.
   */
  readonly agentAliasId?: string;
}

// ---------------------------------------------------------------------------
// Stack
// ---------------------------------------------------------------------------

export class AgentStack extends cdk.Stack {
  /** Full ECR repository URI (without tag) */
  public readonly repositoryUri: string;
  /** ARN of the IAM role assumed by the AgentCore service */
  public readonly executionRoleArn: string;
  /** Name of the CloudWatch log group */
  public readonly logGroupName: string;

  constructor(scope: Construct, id: string, props: AgentStackProps) {
    super(scope, id, props);

    const { environment, imageTag, modelArn, agentRuntimeId, agentAliasId } = props;

    // -----------------------------------------------------------------------
    // ECR Repository
    // -----------------------------------------------------------------------
    // Each environment gets its own repository so that staging and production
    // stacks are fully independent and can be deployed to the same account
    // without a naming conflict.
    //
    // Immutable tags prevent accidental overwrites of a deployed image.
    // scan-on-push surfaces CVEs before the image is ever pulled by AgentCore.
    const repository = new ecr.Repository(this, 'AgentRepository', {
      repositoryName: `ncino-banking-agent-${environment}`,
      imageTagMutability: ecr.TagMutability.IMMUTABLE,
      imageScanOnPush: true,
      // Retain the repository when the stack is destroyed so that existing
      // AgentCore runtimes referencing the images keep working.
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        // Expire untagged (dangling) layers after 1 day so they do not
        // accumulate storage charges from interrupted builds.  UNTAGGED must
        // be priority 1 so the ANY rule below can sit at priority 2.
        {
          rulePriority: 1,
          description: 'Expire untagged images after 1 day',
          tagStatus: ecr.TagStatus.UNTAGGED,
          maxImageAge: cdk.Duration.days(1),
        },
        // Keep the 10 most-recent images of any tag status — protects rollback
        // capability while controlling storage costs.  TagStatus.ANY must have
        // the highest rulePriority value in the policy.
        {
          rulePriority: 2,
          description: 'Keep last 10 images',
          tagStatus: ecr.TagStatus.ANY,
          maxImageCount: 10,
        },
      ],
    });

    this.repositoryUri = repository.repositoryUri;

    // -----------------------------------------------------------------------
    // IAM Execution Role
    // -----------------------------------------------------------------------
    // The AgentCore service assumes this role when pulling and running the
    // container.  Every permission is scoped to the minimum required surface.
    // No explicit roleName — CDK generates a unique physical name so that
    // stack re-creation never collides with an EntityAlreadyExists error.
    // The role ARN is exposed via CfnOutput for downstream automation.
    const executionRole = new iam.Role(this, 'AgentExecutionRole', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      description: `Execution role for the nCino Banking Agent on AgentCore (${environment})`,
    });

    // ECR pull permissions — allows AgentCore to fetch the container image.
    // GetAuthorizationToken is account-scoped and cannot be narrowed further.
    executionRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'EcrPull',
        effect: iam.Effect.ALLOW,
        actions: [
          'ecr:GetDownloadUrlForLayer',
          'ecr:BatchGetImage',
        ],
        resources: [repository.repositoryArn],
      }),
    );

    executionRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'EcrAuthToken',
        effect: iam.Effect.ALLOW,
        actions: ['ecr:GetAuthorizationToken'],
        // GetAuthorizationToken is always account-scoped — resource must be *.
        resources: ['*'],
      }),
    );

    // Bedrock model invocation — scoped to the exact model ARN passed via
    // stack props.  This prevents the execution role from calling any other
    // Bedrock model and satisfies least-privilege requirements.
    executionRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'BedrockInvoke',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [modelArn],
      }),
    );

    // CloudWatch Logs — allow the agent process to emit structured logs.
    executionRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'CloudWatchLogs',
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:CreateLogGroup',
          'logs:CreateLogStream',
          'logs:PutLogEvents',
        ],
        resources: [
          `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/agentcore/ncino-banking-agent/${environment}`,
          `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/agentcore/ncino-banking-agent/${environment}:*`,
        ],
      }),
    );

    this.executionRoleArn = executionRole.roleArn;

    // -----------------------------------------------------------------------
    // CloudWatch Log Group
    // -----------------------------------------------------------------------
    // Explicitly pre-created so that retention and removal policy are under
    // CDK control rather than left to auto-creation with infinite retention.
    const logGroupName = `/aws/agentcore/ncino-banking-agent/${environment}`;

    const logGroup = new logs.LogGroup(this, 'AgentLogGroup', {
      logGroupName,
      // 90 days satisfies the minimum operational and compliance retention
      // requirement for this workload.
      retention: logs.RetentionDays.THREE_MONTHS,
      // RETAIN so that existing log data survives a stack teardown.
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    this.logGroupName = logGroup.logGroupName;

    // -----------------------------------------------------------------------
    // KMS Key for SNS encryption
    // -----------------------------------------------------------------------
    // A dedicated customer-managed key is created per environment so that
    // key policies, rotation, and audit trails are environment-scoped.
    // enableKeyRotation satisfies CIS/NIST automatic annual rotation controls.
    const alertTopicKey = new kms.Key(this, 'AlertTopicKey', {
      description: `KMS key for AgentCore SNS alert topic (${environment})`,
      enableKeyRotation: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // -----------------------------------------------------------------------
    // SNS Alert Topic
    // -----------------------------------------------------------------------
    const alertTopic = new sns.Topic(this, 'AlertTopic', {
      topicName: `agentcore-alerts-${environment}`,
      displayName: `AgentCore alerts — ${environment}`,
      masterKey: alertTopicKey,
    });

    // -----------------------------------------------------------------------
    // CloudWatch Error Count Alarm
    // -----------------------------------------------------------------------
    // Counts ERROR-level entries in the log group via a metric filter, then
    // fires an SNS notification when the threshold is breached.
    const errorMetricFilter = new logs.MetricFilter(this, 'ErrorMetricFilter', {
      logGroup,
      metricNamespace: 'NcinoBankingAgent',
      metricName: `ErrorCount-${environment}`,
      filterPattern: logs.FilterPattern.anyTerm('ERROR', 'Error', 'Exception', 'CRITICAL'),
      metricValue: '1',
      defaultValue: 0,
    });

    const errorMetric = errorMetricFilter.metric({
      period: cdk.Duration.minutes(5),
      statistic: 'Sum',
      label: `Error count (${environment})`,
    });

    const errorAlarm = new cloudwatch.Alarm(this, 'ErrorCountAlarm', {
      alarmName: `ncino-banking-agent-${environment}-error-count`,
      alarmDescription: `Fires when the agent emits ≥5 errors in a 5-minute window (${environment}).`,
      metric: errorMetric,
      threshold: 5,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      actionsEnabled: true,
    });

    errorAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));
    errorAlarm.addOkAction(new cloudwatchActions.SnsAction(alertTopic));

    // -----------------------------------------------------------------------
    // Resource tagging
    // -----------------------------------------------------------------------
    cdk.Tags.of(this).add('Project', 'nCino-AgentCore');
    cdk.Tags.of(this).add('Environment', environment);
    cdk.Tags.of(this).add('ManagedBy', 'CDK');
    cdk.Tags.of(this).add('CostCenter', 'PDE-Africa');
    cdk.Tags.of(this).add('ImageTag', imageTag);

    // -----------------------------------------------------------------------
    // CloudFormation Outputs
    // -----------------------------------------------------------------------
    new cdk.CfnOutput(this, 'EcrRepositoryUri', {
      value: repository.repositoryUri,
      description: 'ECR repository URI (without tag) for the nCino Banking Agent',
      exportName: `ncino-banking-agent-${environment}-ecr-uri`,
    });

    new cdk.CfnOutput(this, 'ExecutionRoleArn', {
      value: executionRole.roleArn,
      description: 'IAM role ARN assumed by AgentCore to run the container',
      exportName: `ncino-banking-agent-${environment}-execution-role-arn`,
    });

    new cdk.CfnOutput(this, 'LogGroupName', {
      value: logGroup.logGroupName,
      description: 'CloudWatch log group receiving agent runtime logs',
      exportName: `ncino-banking-agent-${environment}-log-group-name`,
    });

    new cdk.CfnOutput(this, 'AlertTopicArn', {
      value: alertTopic.topicArn,
      description: 'SNS topic ARN for AgentCore operational alerts',
      exportName: `ncino-banking-agent-${environment}-alert-topic-arn`,
    });

    new cdk.CfnOutput(this, 'DeployedImageTag', {
      value: imageTag,
      description: 'Immutable git SHA tag of the container image deployed in this stack',
    });

    // -----------------------------------------------------------------------
    // SSM Parameters — AgentCore runtime discovery
    // -----------------------------------------------------------------------
    // The rollback script and operations runbook reference these paths to
    // discover the AgentCore runtime ID and alias ID without opening the
    // console.  The values are written with "PENDING" on initial deploy (before
    // the runtime exists) and should be updated by the post-deploy automation
    // that creates / updates the AgentCore runtime and alias.
    const runtimeIdParam = new ssm.StringParameter(this, 'AgentRuntimeIdParam', {
      parameterName: `/ncino/banking-agent/${environment}/agent-runtime-id`,
      stringValue: agentRuntimeId ?? 'PENDING',
      description: `AgentCore runtime ID for the nCino Banking Agent (${environment})`,
      tier: ssm.ParameterTier.STANDARD,
    });

    const aliasIdParam = new ssm.StringParameter(this, 'AgentAliasIdParam', {
      parameterName: `/ncino/banking-agent/${environment}/agent-alias-id`,
      stringValue: agentAliasId ?? 'PENDING',
      description: `AgentCore alias ID for the nCino Banking Agent (${environment})`,
      tier: ssm.ParameterTier.STANDARD,
    });

    new cdk.CfnOutput(this, 'AgentRuntimeIdParamName', {
      value: runtimeIdParam.parameterName,
      description: 'SSM parameter storing the AgentCore runtime ID',
      exportName: `ncino-banking-agent-${environment}-runtime-id-param`,
    });

    new cdk.CfnOutput(this, 'AgentAliasIdParamName', {
      value: aliasIdParam.parameterName,
      description: 'SSM parameter storing the AgentCore alias ID',
      exportName: `ncino-banking-agent-${environment}-alias-id-param`,
    });
  }
}
