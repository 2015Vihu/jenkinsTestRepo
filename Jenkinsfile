pipeline {

    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    environment {

        // UPDATE THIS WITH YOUR ACTUAL FLUTTER PATH
        FLUTTER_HOME = '/Users/Alok/flutter'

        // UPDATE THIS WITH YOUR ACTUAL JAVA PATH
        JAVA_HOME = '/Library/Java/JavaVirtualMachines/jdk-17.jdk/Contents/Home'

        // UPDATE THIS WITH YOUR ACTUAL ANDROID SDK PATH
        ANDROID_HOME = '/Users/Alok/Library/Android/sdk'
        ANDROID_SDK_ROOT = '/Users/Alok/Library/Android/sdk'

        // NODE BIN DIRECTORY (NOT node executable)
        NODE20_BIN = '/opt/homebrew/bin'

        // PATH SETUP
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/cmdline-tools/latest/bin:${JAVA_HOME}/bin:${NODE20_BIN}:${env.PATH}"

        TESTER_EMAIL = 'learningforfuture72@example.com'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Debug Environment') {
            steps {
                sh '''
                    echo "=============================="
                    echo "PATH=$PATH"
                    echo "=============================="

                    echo "FLUTTER_HOME=$FLUTTER_HOME"

                    echo "=============================="
                    echo "Checking Flutter Folder"
                    echo "=============================="

                    ls -la $FLUTTER_HOME || true

                    echo "=============================="
                    echo "Which Flutter"
                    echo "=============================="

                    which flutter || true

                    echo "=============================="
                    echo "Flutter Version"
                    echo "=============================="

                    flutter --version || true

                    echo "=============================="
                    echo "Java Version"
                    echo "=============================="

                    which java || true
                    java -version || true

                    echo "=============================="
                    echo "Android SDK"
                    echo "=============================="

                    ls -la $ANDROID_HOME || true

                    echo "=============================="
                    echo "Node Version"
                    echo "=============================="

                    which node || true
                    node -v || true

                    echo "=============================="
                    echo "Firebase Version"
                    echo "=============================="

                    which firebase || true
                    firebase --version || true
                '''
            }
        }

        stage('Verify Project') {
            steps {
                sh '''
                    pwd
                    ls
                    test -f pubspec.yaml
                    flutter --version
                '''
            }
        }

        stage('Flutter Clean') {
            steps {
                sh 'flutter clean'
            }
        }

        stage('Flutter Pub Get') {
            steps {
                sh 'flutter pub get'
            }
        }

        stage('Flutter Analyze') {
            steps {
                sh 'flutter analyze'
            }
        }

        stage('Flutter Test') {
            steps {
                sh 'flutter test'
            }
        }

        stage('Prepare Android Signing') {
            steps {
                withCredentials([
                    file(credentialsId: 'android-upload-keystore', variable: 'ANDROID_KEYSTORE_FILE'),
                    string(credentialsId: 'android-store-password', variable: 'ANDROID_STORE_PASSWORD'),
                    string(credentialsId: 'android-key-password', variable: 'ANDROID_KEY_PASSWORD'),
                    string(credentialsId: 'android-key-alias', variable: 'ANDROID_KEY_ALIAS')
                ]) {

                    sh '''
                        set +x

                        cp "$ANDROID_KEYSTORE_FILE" android/app/key.jks

                        cat > android/key.properties <<EOF
storePassword=$ANDROID_STORE_PASSWORD
keyPassword=$ANDROID_KEY_PASSWORD
keyAlias=$ANDROID_KEY_ALIAS
storeFile=key.jks
EOF

                        set -x

                        ls -lh android/app
                        test -f android/key.properties
                    '''
                }
            }
        }

        stage('Build Signed Release APK') {
            steps {
                sh 'flutter build apk --release'
            }
        }

        stage('Build Signed Release AAB') {
            steps {
                sh 'flutter build appbundle --release'
            }
        }

        stage('Show Build Outputs') {
            steps {
                sh '''
                    echo "APK outputs:"
                    ls -lh build/app/outputs/flutter-apk || true

                    echo "AAB outputs:"
                    ls -lh build/app/outputs/bundle/release || true
                '''
            }
        }

        stage('Archive Artifacts') {
            steps {
                archiveArtifacts artifacts: '''
                    build/app/outputs/flutter-apk/*.apk,
                    build/app/outputs/bundle/release/*.aab
                ''', fingerprint: true
            }
        }

        stage('Check Firebase CLI') {
            steps {
                sh '''
                    export PATH="$NODE20_BIN:$PATH"

                    which node
                    node -v

                    which firebase
                    firebase --version
                '''
            }
        }

        stage('Upload APK to Firebase App Distribution') {
            steps {
                withCredentials([
                    file(credentialsId: 'firebase-service-account', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                    string(credentialsId: 'firebase-android-app-id', variable: 'FIREBASE_ANDROID_APP_ID')
                ]) {

                    sh '''
                        export PATH="$NODE20_BIN:$PATH"

                        firebase appdistribution:distribute build/app/outputs/flutter-apk/app-release.apk \
                          --app "$FIREBASE_ANDROID_APP_ID" \
                          --release-notes "Jenkins build #${BUILD_NUMBER} from commit ${GIT_COMMIT}" \
                          --testers "$TESTER_EMAIL"
                    '''
                }
            }
        }
    }

    post {

        success {
            echo 'Flutter Android CI/CD pipeline completed successfully.'
        }

        failure {
            echo 'Flutter Android CI/CD pipeline failed.'
        }

        always {
            sh '''
                rm -f android/key.properties
                rm -f android/app/key.jks
            '''
        }
    }
}