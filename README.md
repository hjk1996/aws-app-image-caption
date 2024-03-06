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

- CI/CD  
  
![alt text](../../../Downloads/image_caption_cicd_pipeline.drawio.svg)