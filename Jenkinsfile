pipeline {

    agent any



    options {

        timestamps()

        disableConcurrentBuilds()

        buildDiscarder(logRotator(numToKeepStr: '10'))

    }



    environment {

        NODE20_BIN = '/Users/apple/.nvm/versions/node/v20.19.1/bin'

        TESTER_EMAIL = 'YOUR_TESTER_EMAIL@example.com'

    }



    stages {

        stage('Checkout') {

            steps {

                checkout scm

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



                        cp "$ANDROID_KEYSTORE_FILE" android/app/upload-keystore.jks



                        cat > android/key.properties <<EOF

storePassword=$ANDROID_STORE_PASSWORD

keyPassword=$ANDROID_KEY_PASSWORD

keyAlias=$ANDROID_KEY_ALIAS

storeFile=upload-keystore.jks

EOF



                        set -x

                        ls -lh android/app/*-keystore.jks

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

                rm -f android/app/upload-keystore.jks

            '''

        }

    }

}