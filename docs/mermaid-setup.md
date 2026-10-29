# VSCode에서 ERD 그림 보기

## 설치

VSCode의 **터미널 → 새 터미널**을 열고 아래 명령어를 직접 실행하세요.

```powershell
code --install-extension vstirbu.vscode-mermaid-preview
```

`code`는 VSCode를 명령어로 조작하는 도구이고, `--install-extension`은 확장 프로그램을 설치하라는 뜻입니다. 뒤의 문자열은 **Mermaid Preview** 확장 프로그램의 고유 이름입니다.

이 확장 프로그램은 `.mmd` 파일과 Markdown 안의 Mermaid 도표 미리보기를 지원합니다. Node.js를 별도로 설치할 필요는 없습니다.

## ERD 열기

1. VSCode에서 [erd.mmd](erd.mmd)를 엽니다.
2. `Ctrl + Shift + P`를 눌러 명령 팔레트를 엽니다.
3. `Mermaid Preview: Preview Diagram`을 검색하여 실행합니다.
4. 회원·상품·주문 등의 상자가 연결된 그림이 보이는지 확인합니다.

설명과 그림을 함께 보려면 [table-definition.md](table-definition.md)를 열고 `Ctrl + Shift + V`로 Markdown 미리보기를 여세요.

## code 명령어를 찾을 수 없을 때

VSCode에서 `Ctrl + Shift + X`를 누르고 검색창에 `vstirbu.vscode-mermaid-preview`를 입력한 다음 해당 확장 프로그램을 설치하세요.

## 참고와 작업 상태

- 기능과 미리보기 명령은 [확장 프로그램 공식 저장소](https://github.com/Mermaid-Chart/vscode-mermaid-preview)를 참고했습니다.
- 설치 명령은 사용자가 직접 실행하도록 안내한 것이며, 제가 설치하거나 테스트하지 않았습니다.
