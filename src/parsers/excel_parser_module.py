# excel_parser_module.py
# UI 없이 특정 폴더의 모든 Excel 파일을 지정된 로직으로 처리하는 모듈

import pathlib
import traceback
import json
import sys
import types
import re
import os
import logging
from typing import List, Dict, Any

# xlwings는 Excel과 상호작용하기 위해 필요합니다.
try:
    import xlwings as xw
except ImportError:
    sys.exit("xlwings 라이브러리가 필요합니다. 'pip install xlwings'를 실행해주세요.")

# tqdm은 진행률 표시를 위해 사용됩니다.
try:
    from tqdm import tqdm
except ImportError:
    # tqdm이 없어도 동작은 하지만, 설치를 권장합니다.
    def tqdm(iterable, **kwargs):
        return iterable

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class _ProcessedDocument:
    """
    파싱된 문서 데이터를 담기 위한 내부 클래스입니다.
    langchain.docstore.document.Document의 의존성을 제거하고 독립적으로 작동합니다.
    """
    def __init__(self, page_content, **kwargs):
        self.page_content = page_content
        self.metadata = kwargs.get("metadata", {})

    def __repr__(self):
        """객체를 출력할 때 보기 좋은 형식으로 변환합니다."""
        try:
            metadata_str = json.dumps(self.metadata, indent=2, ensure_ascii=False)
        except TypeError:
            metadata_str = str(self.metadata)
            
        content_summary = (self.page_content[:500] + '...') if len(self.page_content) > 500 else self.page_content
        return f"--- Document ---\n📄 Metadata:\n{metadata_str}\n\n📝 Page Content:\n{content_summary}\n{'='*60}\n\n"

def _extract_shapes_from_workbook(workbook: xw.Book) -> Dict[str, List[Dict[str, Any]]]:
    """
    xlwings를 사용하여 워크북의 모든 시트에서 텍스트가 포함된 도형 정보를 추출합니다.
    그룹화된 도형을 재귀적으로 탐색하여 안정적으로 모든 텍스트를 가져옵니다.
    """
    shapes_by_sheet = {}
    
    def process_shape_collection(shapes, collected_boxes):
        """재귀 함수: 도형 컬렉션을 순회하며 텍스트 상자를 추출합니다."""
        for shape in shapes:
            try:
                if shape.type == 'group':
                    process_shape_collection(shape.group_items, collected_boxes)
                elif shape.text and shape.text.strip():
                    top_left = shape.api.TopLeftCell
                    collected_boxes.append({
                        'text': shape.text.strip(),
                        'row': top_left.Row,
                        'column': top_left.Column
                    })
            except Exception as e:
                logging.warning(f"개별 도형({shape.name}) 처리 중 오류 발생: {e}")

    for sheet in workbook.sheets:
        sheet_shapes = []
        try:
            process_shape_collection(sheet.shapes, sheet_shapes)
            shapes_by_sheet[sheet.name] = sheet_shapes
        except Exception as e:
            logging.error(f"'{sheet.name}' 시트의 도형을 처리하는 중 오류 발생: {e}")
            
    return shapes_by_sheet

def process_folder(folder_path: str, logic_script_path: str) -> List[_ProcessedDocument]:
    """
    지정된 폴더 내의 모든 Excel 파일을 주어진 파서 로직으로 처리합니다.

    Args:
        folder_path (str): 처리할 Excel 파일들이 있는 폴더 경로.
        logic_script_path (str): Excel 파일을 파싱하는 로직이 담긴 Python 스크립트 경로.

    Returns:
        List[_ProcessedDocument]: 파싱된 모든 문서 데이터의 리스트.
    """
    target_folder = pathlib.Path(folder_path)
    logic_file = pathlib.Path(logic_script_path)

    if not target_folder.is_dir():
        logging.error(f"오류: 폴더를 찾을 수 없습니다 - {folder_path}")
        return []
    if not logic_file.is_file():
        logging.error(f"오류: 로직 파일을 찾을 수 없습니다 - {logic_script_path}")
        return []

    # 처리할 엑셀 파일 목록 찾기 (하위 폴더 포함)
    excel_files = [p for p in target_folder.rglob("*.xls*") if p.suffix.lower() in (".xlsx", ".xlsm") and not p.name.startswith("~$")]
    
    if not excel_files:
        logging.warning(f"'{target_folder}' 폴더에 처리할 Excel 파일이 없습니다.")
        return []

    # 파서 로직 스크립트 읽기
    try:
        with open(logic_file, "r", encoding="utf-8") as f:
            parser_code = f.read()
    except Exception as e:
        logging.error(f"로직 파일 '{logic_file.name}'을 읽는 중 오류 발생: {e}")
        return []

    all_results = []
    app = None
    
    # xlwings 앱 인스턴스 시작
    try:
        app = xw.App(visible=False)
        app.display_alerts = False

        for file_path in tqdm(excel_files, desc="Excel 파일 처리 중"):
            workbook = None
            try:
                # 1. Excel 파일 열기
                workbook = app.books.open(str(file_path), read_only=True, update_links=False)

                # 2. 텍스트 상자 데이터 추출
                shapes_data = _extract_shapes_from_workbook(workbook)
                
                # 3. 파서 로직 동적 실행
                # langchain 의존성을 제거하기 위해 가짜 모듈(mock)을 생성
                original_sys_modules = sys.modules.copy()
                mock_langchain = types.ModuleType('langchain')
                mock_docstore = types.ModuleType('langchain.docstore')
                mock_document_module = types.ModuleType('langchain.docstore.document')
                mock_document_module.Document = _ProcessedDocument
                mock_langchain.docstore = mock_docstore
                mock_docstore.document = mock_document_module
                sys.modules.update({
                    'langchain': mock_langchain, 
                    'langchain.docstore': mock_docstore, 
                    'langchain.docstore.document': mock_document_module
                })

                parser_module = types.ModuleType("dynamic_parser")
                exec(parser_code, parser_module.__dict__)
                
                if hasattr(parser_module, '_parse_workbook'):
                    parse_function = getattr(parser_module, '_parse_workbook')
                    # 파서 함수에 파일 경로와 추출된 도형 정보 전달
                    documents = parse_function(file_path, shapes_by_sheet=shapes_data)
                    all_results.extend(documents)
                    logging.info(f"'{file_path.name}' 처리 완료. {len(documents)}개 문서 생성.")
                else:
                    logging.warning(f"'{logic_file.name}'에 '_parse_workbook' 함수가 없어 '{file_path.name}' 파일을 건너뜁니다.")

            except Exception as e:
                logging.error(f"'{file_path.name}' 파일 처리 중 오류 발생:\n{traceback.format_exc()}")
            finally:
                if workbook:
                    workbook.close()
                # 시스템 모듈 원상 복구
                sys.modules.clear()
                sys.modules.update(original_sys_modules)

    except Exception as e:
        logging.error(f"xlwings 앱 시작 중 오류 발생: {e}")
    finally:
        if app:
            app.quit()
            
    return all_results

if __name__ == '__main__':
    # 이 모듈을 직접 실행할 때의 예시입니다.
    # 1. 처리할 Excel 파일이 있는 폴더 경로
    # UNC 경로 (네트워크 경로)도 지원합니다.
    TARGET_FOLDER_PATH = r'\\203.228.239.6\선체생산\101) [혁신기술]_____DM, AI, BIG DATA, PALANTIR FOUNDRY, IoT, 로봇\012 RapidMiner\RAG 학습파일\선각계열회의\excel\2025년 회의록'
    
    # 2. 파싱 로직이 담긴 스크립트 파일 경로
    # 이 스크립트가 있는 위치를 기준으로 상대 경로를 사용합니다.
    CURRENT_DIR = pathlib.Path(__file__).parent
    LOGIC_FILE_PATH = str(CURRENT_DIR / 'parsers' / '01_seongak_parser.py')

    print(f"대상 폴더: {TARGET_FOLDER_PATH}")
    print(f"로직 파일: {LOGIC_FILE_PATH}")
    print("-" * 30)
    
    # 모듈의 메인 함수 실행
    parsed_documents = process_folder(TARGET_FOLDER_PATH, LOGIC_FILE_PATH)

    print("-" * 30)
    print(f"총 {len(parsed_documents)}개의 문서(Document)를 성공적으로 파싱했습니다.")

    # 결과 확인 (처음 3개만 출력)
    if parsed_documents:
        print("\n--- 파싱 결과 샘플 ---")
        for doc in parsed_documents[:3]:
            print(doc)