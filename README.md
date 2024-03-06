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

- **CI/CD**

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