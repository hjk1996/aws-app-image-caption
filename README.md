# Amazon PhotoQuery (Image Caption Generator App)

## 프로젝트 개요

Amazon PhotoQuery는 클라우드 기반 사진 앨범 서비스로, 사용자가 저장된 사진을 쉽게 검색하고 관리할 수 있도록 돕는 모바일 앱입니다. 웹 플랫폼에서 동작하며, AI 기반의 검색 기능을 제공합니다.
k

## 주요 기능

- **이미지 캡션**: 인공지능 모델을 이용해 이미지에 대한 캡션을 생성하고 저장합니다.
- **캡션 벡터 변환**: 캡션을 텍스트 임베딩 모델을 이용해 벡터로 변환하고 저장합니다. 저장된 벡터는 Semantic Search를 위해 사용됩니다.

## 데모 영상

[![Video Title](http://img.youtube.com/vi/l_XaYF5AkM4/0.jpg)](https://www.youtube.com/watch?v=l_XaYF5AkM4 "Video Title")

## 아키텍처

<img src="./image_caption_architecture.drawio.svg">

### 개요

본 애플리케이션은 AWS S3에 이미지가 업로드되는 이벤트를 감지하여 자동으로 이미지에 대한 캡션을 생성하고, 생성된 캡션을 벡터로 변환하여 Amazon DocumentDB에 저장하는 과정을 담당합니다. 이 아키텍처는 AWS S3, SNS, SQS, EKS, NAT Gateway, 그리고 DocumentDB를 활용합니다.

### 아키텍처 컴포넌트

1. Amazon S3: 이미지 파일 저장소로 사용되며, 새로운 이미지 업로드 시 이벤트를 발생시킵니다.
2. Amazon SNS (Simple Notification Service): S3에서 발생한 이미지 업로드 이벤트를 수신하고 해당 이벤트를 Amazon SQS로 전달합니다.
3. Amazon SQS (Simple Queue Service): SNS로부터 받은 메시지를 큐잉하여 처리를 대기합니다. 이는 메시지 처리의 탄력성을 보장합니다.
4. Amazon EKS (Elastic Kubernetes Service): 이미지 처리 및 캡션 생성 애플리케이션을 실행합니다. EKS worker node는 Private Subnet에 배치되어 외부 인터넷과의 통신을 위해 NAT Gateway를 사용합니다.
5. NAT Gateway: EKS worker node가 인터넷과 통신(예: S3에서 이미지 다운로드, 외부 API 호출 등)할 수 있게 하는 역할을 합니다. Public Subnet에 위치합니다.
6. 인공지능 모델(blip-image-captioning-large): 이미지 캡션을 생성하기 위한 AI 모델입니다. 이 모델은 EKS의 워커 노드에서 실행되며, S3로부터 다운로드 받은 이미지에 대한 캡션을 생성합니다.
7. 텍스트 임베딩 모델(all-MiniLM-L6-v2): 생성된 캡션을 수치적 벡터로 변환하는데 사용됩니다. 이 벡터는 검색 작업을 위해서 사용합니다.
8. Amazon DocumentDB: 생성된 캡션과 해당 벡터를 저장하는 NoSQL 문서 데이터베이스입니다. 프라이빗 서브넷 내에 위치하며, EKS worker node로부터 접근 가능합니다.

### 데이터 플로우

1. 사용자가 업로드한 이미지가 S3에 저장됩니다.
2. S3 업로드 이벤트는 Amazon SNS 토픽으로 전송됩니다.
3. SNS 토픽은 연결된 SQS 큐에 메시지를 전달합니다.
4. EKS 클러스터 내의 애플리케이션이 SQS 큐에서 메시지를 폴링하고 처리합니다.
5. 애플리케이션은 메시지에서 이미지 정보를 추출하고, S3에서 이미지를 다운로드합니다.
6. 인공지능 모델을 통해 이미지에 대한 캡션을 생성하고, 생성된 캡션을 텍스트 임베딩 모델을 통해 벡터로 변환합니다.
7. 마지막으로, 생성된 캡션과 벡터는 DocumentDB Cluster에 저장됩니다.

## CI/CD

<img src="./image_caption_cicd_pipeline.drawio.svg">

1. **코드 푸시**
   - 개발자는 변경된 코드를 GitHub 리포지토리에 푸시합니다.
2. **Jenkins 빌드 트리거**
   - GitHub 웹훅을 통해 Jenkins 서버에서 빌드가 트리거됩니다.
3. **컨테이너 이미지 빌드 및 업로드**
   - Jenkins 서버에서 컨테이너 이미지를 빌드하고 이미지 레지스트리에 업로드합니다.
   - 동시에, deployment manifest 파일이 저장된 별도의 GitHub 리포지토리에서 deployment manifest를 업데이트합니다.
4. **ArgoCD를 통한 배포 관리**
   - ArgoCD는 manifest 파일이 저장된 GitHub 리포지토리를 지속적으로 모니터링합니다.
   - 업데이트가 감지되면, ArgoCD는 변경사항을 바탕으로 Kubernetes의 Deployment를 업데이트합니다.
   - 이 과정은 이미지 레지스트리에서 새롭게 빌드된 이미지를 다운로드하고, 해당 이미지를 Amazon EKS 클러스터에 배포함으로써 완료됩니다.
****