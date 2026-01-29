# 미뤄둔 작업 전체 목록

**업데이트**: 2026-01-29 10:36

---

## 🔴 높은 우선순위 (파이프라인 영향)

### 1. Step 2-5 완료 후 섹터 필터 누락 확인
**문제**: Step 1은 전체 티커 수집, Step 2에서 섹터 필터 적용  
**확인 필요**: Financial/Utilities/Energy/Materials 제외 확인  
**타이밍**: Step 2 완료 후 (오늘 14:30)

---

## 🟡 중간 우선순위 (품질 개선)

### 2. 생존 편향 해결
**현재 상태**: 100% 편향 (현재 상장된 티커만)  
**해결 방법**:
- S&P 500 Historical Constituents 확보
- 또는 상장폐지 티커 수동 추가
- 백테스트 재실행

**영향**: 성과가 과대평가될 가능성  
**우선순위**: 중간 (정확도 향상)

### 3. Git 커밋 누락
**커밋 필요**:
- US 전체 시장 확장 코드 (`step1_price_collector_sequential.py`)
- 7,908개 티커 데이터 (메타 정보)
- 문서 업데이트 (CHANGELOG, task.md 등)

**타이밍**: 파이프라인 완료 후

---

## 🟢 낮은 우선순위 (선택적)

### 4. meta.json 타입 에러 수정
**파일**: `data_collection/step1_price_collector_sequential.py`  
**라인**: 175, 206  
**영향**: 없음 (디버깅용만)  
**수정 시간**: 1분

### 5. 가중치 변화 시각화
**현재**: `step4_weights_history.csv` 생성됨  
**미완료**: 시각화 코드 없음  
**추가 작업**:
```python
import matplotlib.pyplot as plt
weights = pd.read_csv('step4_weights_history.csv')
weights.plot(x='FiscalYear', y=['w_m1', 'w_m2', 'w_m3'])
plt.savefig('weights_trend.png')
```

### 6. 문서 정리
**대기 중**:
- [ ] walkthrough.md 최종 업데이트 (7,908개 결과)
- [ ] CHANGELOG.md 정리 (US 시장 확장 추가)
- [ ] README.md 작성 (프로젝트 소개)
- [ ] 아티팩트 정리 (불필요한 .md 파일 삭제)

**타이밍**: 백테스트 완료 후

### 7. Plan B 파일 정리
**삭제됨**: `step1_price_collector_alt.py` ✅  
**추가 정리**:
- `/tmp/*.log` 파일들 정리
- `data_cache/checkpoints/` 폴더 (이미 삭제됨 ✅)

---

## 🔵 장기 과제 (나중에)

### 8. 코드 리팩토링
**개선 가능**:
- 중복 코드 제거
- 함수 분리 (Step 1-5 공통 로직)
- 타입 힌팅 추가
- Docstring 개선

### 9. 성능 최적화
**아이디어**:
- Step 2 병렬 처리 (SEC API 허용 시)
- 캐싱 개선
- 메모리 사용량 줄이기

### 10. 추가 분석
**미완료**:
- 섹터별 성과 비교
- 시가총액별 성과 비교
- 가중치 변화 패턴 분석
- 실패 예측 사례 분석

---

## 📋 작업 우선순위 요약

### 지금 (자동 실행 중)
- [/] Step 2-5 파이프라인

### 오늘 (파이프라인 완료 후)
1. ✅ 섹터 필터 결과 확인
2. ✅ 백테스트 성과 확인
3. ✅ Git 커밋

### 이번 주
1. 생존 편향 해결 방안 검토
2. 문서 정리
3. 가중치 시각화

### 나중에
1. meta.json 에러 수정
2. 코드 리팩토링
3. 추가 분석

---

## ⚠️ 잊지 말아야 할 것

1. **섹터 필터 확인**: Step 2 완료 후 Financial 등 제외 확인
2. **Git 커밋**: 오늘 작업 내용 기록
3. **백업 유지**: `step1_meta_sp500_backup.json` 보존
