pipeline {
    agent any

    environment {
        DOCKER_IMAGE = 'heart2709/proxmox-app'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Prepare image tag') {
            steps {
                script {
                    // BRANCH_NAME is set by Multibranch Pipeline. GIT_BRANCH
                    // supports the existing single-branch Pipeline job.
                    def sourceBranch = env.BRANCH_NAME ?: (env.GIT_BRANCH ?: '')
                    sourceBranch = sourceBranch
                        .replaceFirst(/^refs\/remotes\/origin\//, '')
                        .replaceFirst(/^refs\/heads\//, '')
                        .replaceFirst(/^origin\//, '')

                    def safeBranch = sourceBranch.replaceAll(/[^A-Za-z0-9_.-]/, '-').take(70)
                    if (!safeBranch) {
                        safeBranch = 'unknown'
                    }

                    env.BRANCH_IMAGE = "${env.DOCKER_IMAGE}:${safeBranch}-${env.BUILD_NUMBER}"
                    env.DEPLOY_MAIN = sourceBranch == 'main' ? 'true' : 'false'
                    echo "Building branch '${sourceBranch}' as ${env.BRANCH_IMAGE}"
                    echo "Publish and deploy enabled: ${env.DEPLOY_MAIN}"
                }
            }
        }

        stage('Build Docker image') {
            steps {
                sh 'docker build --pull -t "$BRANCH_IMAGE" .'
            }
        }

        stage('Publish main image') {
            when {
                expression { env.DEPLOY_MAIN == 'true' }
            }
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-credentials',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh '''
                        set +x
                        export DOCKER_CONFIG="$(mktemp -d)"
                        trap 'docker logout >/dev/null 2>&1 || true; rm -rf "$DOCKER_CONFIG"' EXIT
                        printf '%s' "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
                        docker push "$BRANCH_IMAGE"
                        docker tag "$BRANCH_IMAGE" "$DOCKER_IMAGE:latest"
                        docker push "$DOCKER_IMAGE:latest"
                    '''
                }
            }
        }

        stage('Deploy main to Kubernetes') {
            when {
                expression { env.DEPLOY_MAIN == 'true' }
            }
            steps {
                sh '''
                    kubectl apply -f deployment.yaml
                    kubectl rollout restart deployment/proxmox-app
                    kubectl rollout status deployment/proxmox-app --timeout=180s
                '''
            }
        }
    }
}

