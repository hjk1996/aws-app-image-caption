pipeline {
    agent any

    environment {
        ECR_URL = "109412806537.dkr.ecr.us-east-1.amazonaws.com/app-image-caption"
        GITCREDENTIAL = "khj-github" 
        GITSSHADD = "git@github.com:hjk1996/aws-app-eks-manifests.git"
        GITEMAIL = "dunhill741@naver.com"
        GITNAME = "hjk1996"
    }


    stages {
        stage('Checkout') {
            steps {
                // GitHub에서 최신 코드를 체크아웃
                checkout scm
            }

            post {
                success {
                    echo "Success Checkout!"
                }
                failure {
                    echo "Failure Checkout!"
                }
            }
        }
        stage('Build Docker Image') {
            steps {
                // Docker 이미지 빌드
                sh "docker build -t ${ECR_URL}:${currentBuild.number} ."
                sh "docker tag ${ECR_URL}:${currentBuild.number} ${ECR_URL}:latest"
            }

            post {
                success {
                    echo "Success Docker Image Build!"
                }
                failure {
                    echo "Failure Docker Image Build!"
                }
            }
        }
        stage('Push to ECR') {
            steps {
                // ECR에 로그인
                sh 'aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${ECR_URL}'
                // 이미지 푸시
                sh "docker push ${ECR_URL}:${currentBuild.number}"
                sh "docker push ${ECR_URL}:latest"
            }

            post {

                always {
                    sh "docker image rm ${ECR_URL}:${currentBuild.number}"
                    sh "docker image rm ${ECR_URL}:latest"
                }

                success {
                    echo "Success Push to ECR"
                }
                failure {
                    echo "Failure Push to ECR"
                }
            }
        }

        stage('k8s manifest file update') {
      	   steps {
                git credentialsId: GITCREDENTIAL,
                    url: GITSSHADD,
                    branch: 'main'
            
                // 이미지 태그 변경 후 메인 브랜치에 푸시
                sh "git config --global user.email ${GITEMAIL}"
                sh "git config --global user.name ${GITNAME}"
                sh "sed -i 's@${ECR_URL}:.*@${ECR_URL}:${currentBuild.number}@g' image_caption/image_caption_deployment.yaml"
                echo "edit k8s deployment manifest file!"
                sh "git checkout main"
                sh "git add ."
                sh "git commit -m 'fix:${ECR_URL}:${currentBuild.number} image versioning'"
                sh "git remote remove origin"
                sh "git remote add origin ${GITSSHADD}"
                echo "push to main branch"
                sh "git push -u origin main"

      	   }
      	   post {
                failure {
                   echo 'k8s manifest file update failure'
                }
                success {
                    echo 'k8s manifest file update success'  
                }
  	 }
}

    }
}