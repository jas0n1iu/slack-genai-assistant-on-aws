# 基于Amazon Bedrock构建Slack图像生成助手App

## **引言**

在当今的商业环境中，视觉内容变得越来越重要。无论是营销材料、产品演示还是客户交流，引人入胜的图像和视觉效果都可以提高内容的吸引力和影响力。然而，创建高质量的视觉内容通常需要专业的设计技能和昂贵的工具，这对于许多企业来说是一个挑战。

在本文中，我们将介绍如何基于 Amazon Bedrock托管的SDXL基础模型构建一个 Slack 图像生成助手App。该Slack App允许 Slack 用户通过发送文本提示来请求生成图像，并将生成的图像直接发送到 Slack 频道。这不仅为团队提供了一种创建视觉内容的简单方式，而且还可以促进协作和讨论。

Amazon Bedrock 是一项完全托管的基础模型（FM）服务，通过单个 API 提供来自 AI21 Labs、Anthropic、Cohere、Meta、Mistral AI、Stability AI 和 Amazon 等领先人工智能公司的高性能基础模型，以及通过安全性、隐私性和负责任的人工智能构建生成式人工智能应用程序所需的一系列广泛功能。由于 Amazon Bedrock 是无服务器的，因此您无需管理任何基础设施，并且可以使用已经熟悉的 AWS 服务将生成式人工智能功能安全地集成和部署到您的应用程序中。

## 解决方案概述

在这篇博客中，我们将介绍如何在 AWS Lambda 中部署Slack 网关服务，用于接收 Slack 消息并使用 Amazon Bedrock 及其托管的Stability AI SDXL 基础模型生成相应的图像。我们利用了多个 Amazon云服务来构建一个健壮的解决方案：Secrets Manager 用于安全地存储密钥，DynamoDB 用于防止重复消息处理，S3 Bucket和 CloudFront 用于存储和分发生成的图像。通过将所有这些服务与 AWS Lambda 结合使用，我们可以构建一个无服务器的、可扩展的应用程序，用于处理 Slack 消息并生成图像。

![Architecture Overview](https://github.com/jas0n1iu/slack-genai-assistant-on-aws/blob/main/images/Architecture.png)

## 先决条件

- 可用的亚马逊云科技账户
- Amazon Bedrock Stable AI SDXL基础模型服务已启
- 已创建 私有的S3 Bucket用于存储生成的图像
- 通过CloudFront 分发私有S3 Bucket中的图像，实现静态内容加速，同时也可以配置CloudFront实现API Gateway动态加速

## 创建Slack App

在 Slack 工作区中创建一个新的 Slack 应用程序，启用 "im:history"、"chat:write" 和 "commands" 作用域，具体步骤如下：

1 打开https://api.slack.com/apps/new 并选择"From a manifest"：

![image.png](https://prod-files-secure.s3.us-west-2.amazonaws.com/35a8c96c-fea9-4dde-b6a3-d9d9079f17ad/2e658257-5461-4f80-acfa-04b91de71a99/image.png)

2 选择要将应用程序安装到的工作区

3  将 以下yaml格式的template的内容复制到文本框中（在 YAML选项卡内），然后单击“下一步”

```yaml
display_information:
  name: SDXL
features:
  app_home:
    home_tab_enabled: true
    messages_tab_enabled: false
    messages_tab_read_only_enabled: false
  bot_user:
    display_name: SDXL
    always_online: false
oauth_config:
  scopes:
    bot:
      - im:read
      - im:write
      - chat:write
      - app_mentions:read
      - im:history
      - incoming-webhook
settings:
  event_subscriptions:
    request_url: https://tobemodified.com
    bot_events:
      - app_home_opened
      - app_mention
      - message.im
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
```

![image.png](https://prod-files-secure.s3.us-west-2.amazonaws.com/35a8c96c-fea9-4dde-b6a3-d9d9079f17ad/512e5c17-fa02-4bfd-aff6-3465c4a974a6/image.png)

4 查看配置，然后单击“Create”

完成App创建后，查看**Signing Secret**，接下来会通过Cloudformation保存到Secret Manager中。

![image.png](https://prod-files-secure.s3.us-west-2.amazonaws.com/35a8c96c-fea9-4dde-b6a3-d9d9079f17ad/a9b74f84-4059-47aa-89b9-1aa71f41b98e/image.png)

5 选择左边栏OAuth & Permissions，点击Install to Workspace，然后点击Allow

![image.png](https://prod-files-secure.s3.us-west-2.amazonaws.com/35a8c96c-fea9-4dde-b6a3-d9d9079f17ad/679f96cc-1dc9-4e7a-8286-4e17c1454080/image.png)

查看生成的OAuth Token，接下来会通过Cloudformation保存到Secret Manager中。

![image.png](https://prod-files-secure.s3.us-west-2.amazonaws.com/35a8c96c-fea9-4dde-b6a3-d9d9079f17ad/78b6a8c0-8278-4440-9161-a6f5fbbe74cf/image.png)

## 创建Amazon云服务

我们将使用 CloudFormation 来部署所需的Amazon云服务，包括 Lambda 函数、API Gateway、Secrets Manager 和 DynamoDB。CloudFormation 模板将自动配置所有必需的资源，简化了部署过程。

点击Launch Stack以创建Cloudformation 堆栈

[![Launch Stack](https://cdn.rawgit.com/buildkite/cloudformation-launch-stack-button-svg/master/launch-stack.svg)](https://console.aws.amazon.com/cloudformation/home?#/stacks/create/review?templateURL=https://s3.us-west-2.amazonaws.com/examplelabs.net/template/cf-slack-app.yaml&stackName=SlackAppSDXL)

依次填写用于保存Bedrock SDXL产生的图片的私有S3 Bucket、用于分发图片的Cloudfronnt 分配、Slack App签名密钥、Slack App OAuth Token，勾选**acknowledge，**然后**Create stack。**

![image.png](https://prod-files-secure.s3.us-west-2.amazonaws.com/35a8c96c-fea9-4dde-b6a3-d9d9079f17ad/913355dc-ddd6-40ef-9f7a-b88ccb5a4575/image.png)

Stack创建完成后，复制SlackAPIGatewayEndpoint

![image.png](https://prod-files-secure.s3.us-west-2.amazonaws.com/35a8c96c-fea9-4dde-b6a3-d9d9079f17ad/a89e4f88-96bc-42fc-a7e1-ece3b0e2d2f7/image.png)

将SlackAPIGatewayEndpoint配置为事件订阅的请求 URL，替换模版中的默认值，如果显示Verified表示Slack App连接Lambda 函数成功，点击Save Changes。

![image.png](https://prod-files-secure.s3.us-west-2.amazonaws.com/35a8c96c-fea9-4dde-b6a3-d9d9079f17ad/cbb8bdc1-7792-4147-b40d-0feda6d9f072/image.png)

### Lambda函数介绍

Lambda 函数将处理来自 Slack 的事件，调用 Amazon Bedrock 生成图像，并将图像上传到 S3 存储桶。该函数首先验证 Slack 签名以确保请求来自 Slack。然后，它处理 URL 验证挑战或实际的 Slack 消息事件。对于消息事件，它会将客户端消息 ID 和时间戳写入 DynamoDB 表，以防止重复处理。

```python
import json
import boto3
# import ...

def handler(event, context):
    event_body = json.loads(event.get("body"))
    response = None

    # Verify the Slack signature
    if not verify_slack_signature(event['headers'], event['body']):
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Invalid Slack signature'})
        }

    if event_body.get("type") == "url_verification":
        response = {
            'statusCode': 200,
            'body': event_body['challenge']
        }
    else:
        client_msg_id = event_body['event']['client_msg_id']
        try:
            table.put_item(
                Item={
                    'client_msg_id': client_msg_id,
                    'timestamp': int(time.time())  # Add a timestamp for replay attack prevention
                },
                ConditionExpression='attribute_not_exists(client_msg_id)'
            )

            response = handle_message(event_body)

        except ClientError as e:
            if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                return {
                    'statusCode': 200,
                    'body': json.dumps('Event already processed')
                }
    return response
```

`handle_message` 函数提取实际的消息文本，调用 `call_bedrock` 函数生成图像，并将生成的图像 URL 发送回 Slack 频道。

```python
def handle_message(slack_body):
    slack_text = slack_body.get('event').get('text')
    slack_user = slack_body.get('event').get('user')
    channel = slack_body.get('event').get('channel')

    pattern = r'<@\w+>\s*(.+)'
    match = re.search(pattern, slack_text)
    if match:
        slack_text = match.group(1)

    image_url = call_bedrock(slack_text)

    data = {
        'channel': channel,
        'blocks': [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{slack_user}> Generated Image:"
                }
            },
            {
                "type": "image",
                "image_url": image_url,
                "alt_text": "Generated Image"
            }
        ]
    }

    headers = {'Authorization': f'Bearer {slack_token}', 'Content-Type': 'application/json'}
    http.request('POST', slack_api_url, headers=headers, body=json.dumps(data))

    return {'statusCode': 200, 'body': json.dumps({'msg': "message received"})}
```

`call_bedrock` 函数调用 Amazon Bedrock 服务生成图像，并将生成的图像上传到 S3 存储桶，并返回 CloudFront 分发的图像 URL。

```python
def call_bedrock(question):
    client = boto3.client("bedrock-runtime")
    model_id = "stability.stable-diffusion-xl-v1"

    native_request = {
        "text_prompts": [{"text": question}],
        "style_preset": "photographic",
        "seed": random.randint(0, 4294967295),
        "cfg_scale": 10,
        "steps": 30,
    }

    request = json.dumps(native_request)

    try:
        response = client.invoke_model(modelId=model_id, body=request)
    except Exception as e:
        print(f"Error calling Bedrock AI model: {e}")
        return "Sorry, I'm having trouble processing your request right now."

    model_response = json.loads(response["body"].read())
    base64_image_data = model_response["artifacts"][0]["base64"]

    image_key = f"{S3_PREFIX}{str(uuid.uuid4())}.png"
    s3_client.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=image_key,
        Body=base64.b64decode(base64_image_data),
        ContentType="image/png"
    )

    image_url = f"https://{CLOUDFRONT_NAME}/{image_key}"

    return image_url
```

## 验证Slack App

现在，您可以在 Slack 频道中发送消息，Lambda 函数将调用 Amazon Bedrock 生成相应的图像，并将图像发送回 Slack 频道。通过@SlackAppName + 提示词的方式向App提问，第1次使用的时候，需要点击Invite Them，手机App输给效果如下：

![IMG_6483.jpg](https://prod-files-secure.s3.us-west-2.amazonaws.com/35a8c96c-fea9-4dde-b6a3-d9d9079f17ad/22b2e872-7c28-43ca-aa8c-ebbe2d781913/IMG_6483.jpg)

选择Invite Them后，Slack App SDXL根据提示词输出了图片：

![IMG_6484.jpg](https://prod-files-secure.s3.us-west-2.amazonaws.com/35a8c96c-fea9-4dde-b6a3-d9d9079f17ad/61c57021-bae5-4e2d-ba46-df2801926386/IMG_6484.jpg)

## 总结

通过Amazon Cloudformation部署了所需的云服务之后，您需要将 API Gateway 端点配置为 Slack App的事件订阅 URL。然后，每当 Slack 用户在频道中发送文本提示时，Lambda 函数就会被触发，调用 Bedrock 服务生成相应的图像，并将图像发送回 Slack 频道。通过利用Amazon Bedrock以及Lambda、API Gateway、Secrets Manager 和 DynamoDB等服务的强大功能，您可以轻松构建一个功能强大的 、基于无服务器架构的、Slack 图像生成助手App。这不仅可以提高团队的工作效率，还可以激发创造力，促进更好的协作和沟通。

## **参考资料**

[Slack Quickstart: Send a mesage](https://api.slack.com/quickstart)

[Verifying requests from Slack](https://api.slack.com/authentication/verifying-requests-from-slack)

[Invoke Stable Diffusion XL on Amazon Bedrock to generate an image](https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-runtime_example_bedrock-runtime_InvokeModel_StableDiffusion_section.html)
