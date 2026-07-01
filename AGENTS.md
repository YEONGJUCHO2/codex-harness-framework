# 프로젝트: {프로젝트명}

## 기술 스택
- {프레임워크 (예: Next.js 15)}
- {언어 (예: TypeScript strict mode)}
- {스타일링 (예: Tailwind CSS)}

## 아키텍처 규칙
- CRITICAL: {절대 지켜야 할 규칙 1 (예: 모든 API 로직은 app/api/ 라우트 핸들러에서만 처리)}
- CRITICAL: {절대 지켜야 할 규칙 2 (예: 클라이언트 컴포넌트에서 직접 외부 API를 호출하지 말 것)}
- {일반 규칙 (예: 컴포넌트는 components/ 폴더에, 타입은 types/ 폴더에 분리)}
- CRITICAL: 루트 AGENTS.md는 핵심 규칙만 담고 300줄 이하로 유지할 것. 상세 설명은 docs/ 또는 phases/{phase}/AGENTS.md로 분리할 것.
- CRITICAL: phases/{phase}/AGENTS.md가 존재할 경우 해당 phase의 추가 규칙으로 적용하되, 루트 AGENTS.md의 CRITICAL 규칙과 충돌할 수 없음.

## 개발 프로세스
- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성할 것 (TDD)
- CRITICAL: `rm -rf`, `git push --force`, `git reset --hard`, `DROP TABLE` 같은 고위험 명령은 직접 실행하지 말 것. `.codex/hooks/deny-dangerous-command.sh`가 이를 차단한다.
- CRITICAL: 구현 세션은 lint/build/test를 직접 실행하고 step을 completed로 표시하지 말 것. 구현 및 검증 완료 시 ready_for_completion까지만 기록하고, completed는 하네스 executor만 기록할 것.
- 커밋 메시지는 conventional commits 형식을 따를 것 (feat:, fix:, docs:, refactor:)

## 명령어
npm run dev      # 개발 서버
npm run build    # 프로덕션 빌드
npm run lint     # ESLint
npm run test     # 테스트
