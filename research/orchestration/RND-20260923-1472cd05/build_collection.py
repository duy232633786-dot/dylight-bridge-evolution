"""Đóng gói ghi chú nghiên cứu; không thực thi thuật toán thiết kế hoặc sửa vault."""
import hashlib
import json
import re
import shutil
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

ROOT=Path(__file__).parent
REPO=ROOT.parents[2]
SCRATCH=REPO.parent/'artifacts'/'sage_research_20260923'
PUB=ROOT/'publication'
VAULT=Path(r'D:\Obsidian Vault')
COLLECTION='DYLIGHT Bridge Evolution/Literature/SAGE-EvoBridge Research 2026-09-23'
DATE='2026-09-23'
INDEX='00 - Thu vien nghien cuu quoc te SAGE-EvoBridge'
READING={'SELECTED_SECTIONS_READ':'Đã đọc một số phần','OFFICIAL_PAGE_READ':'Đã đọc trang chính thức','ABSTRACT_READ':'Đã đọc tóm tắt','METADATA_ONLY':'Chỉ thư mục/chỉ mục'}
for p in [PUB/'Sources',PUB/'Attachments',PUB/'Data',ROOT/'source_batches']:
    p.mkdir(parents=True,exist_ok=True)
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def md(name,text):(PUB/(name+'.md')).write_text(text.strip()+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm_url(u):
    if not u:return ''
    x=urlsplit(unquote(u.strip()).lower());return urlunsplit(('',x.netloc.removeprefix('www.'),x.path.rstrip('/'),x.query,''))
def norm_title(t):return re.sub(r'[^a-z0-9]+','',unicodedata.normalize('NFKD',t).encode('ascii','ignore').decode().lower())
def norm_doi(d):return (d or '').lower().removeprefix('https://doi.org/').strip()
def wik(name,label=None,table=False):
    label=(label or name).replace('|',' / ').replace('[','(').replace(']',')')
    return '[['+COLLECTION+'/'+name+('\\|' if table else '|')+label+']]'
def ref(s,table=False):return wik('Sources/'+s['id'],s['id']+' — '+s['title'],table)
def refs(ids):return ' · '.join(wik('Sources/'+i,i) for i in ids)

batches={}
sources=[]
for filename in ['standards.json','bridges_materials.json','ai_construction.json','geometry.json']:
    data=json.loads((SCRATCH/filename).read_text(encoding='utf-8'))
    batches[filename]=data;dump(ROOT/'source_batches'/filename,data)
    for s in data['sources']:
        s['batch']=filename.removesuffix('.json');sources.append(s)
assert len({s['id'] for s in sources})==len(sources)
sources.sort(key=lambda s:s['id'])
byid={s['id']:s for s in sources}
legacy=json.loads((REPO/'research/literature/index.json').read_text(encoding='utf-8'))
old=legacy['references']
old_urls=json.loads((SCRATCH/'existing_urls.json').read_text(encoding='utf-8'))
if isinstance(old_urls,dict):old_urls=old_urls.get('urls',[])
old_urlset={norm_url(x) for x in old_urls if isinstance(x,str)}

download_records=[]
for s in sources:
    # Nhận diện tài liệu TCVN theo số hiệu/tệp, không gộp theo URL danh mục chung.
    s['canonical_document_key']='TCVN-'+s['id'][3:] if s.get('local_existing_path') else ('IFC4.3.2.0' if s['id'] in ['AI-018','GE-019'] else norm_doi(s.get('doi')) or norm_url(s['url']))
    s['evidence_status']='UNVERIFIED_REFERENCE'
    s['claim_ceiling']='IDEA'
    s['engineering_rule_approved']=False
    s['training_rights']='NOT_ASSESSED' if s['id']!='ST-001' else 'PUBLISHER_RESTRICTS_AI_USE'
    s['ingestion_policy']=s.get('ingestion_policy','RESEARCH_NOTES_ONLY; reassess rights before automated full-text ingestion or training')
    matches=[]
    for o in old:
        same_doi=bool(norm_doi(s.get('doi'))) and norm_doi(s.get('doi'))==norm_doi(o.get('doi'))
        same_title=norm_title(s['title'])==norm_title(o['title'])
        same_url=not s.get('local_existing_path') and norm_url(o.get('url')) in {norm_url(s['url']),norm_url(s.get('pdf_url'))}
        if same_doi or same_title or same_url:matches.append({'id':o['reference_id'],'basis':'DOI' if same_doi else 'TITLE' if same_title else 'URL'})
    s['legacy_matches']=matches
    if s.get('local_existing_path'):s['library_relation']='EXISTING_LOCAL_STANDARD'
    elif matches or norm_url(s['url']) in old_urlset or norm_url(s.get('pdf_url')) in old_urlset:s['library_relation']='MATCHES_EXISTING_LIBRARY'
    else:s['library_relation']='NO_EXACT_MATCH_IN_PRIOR_INDEX'
    candidates=[ROOT/'downloads'/(s['id']+'.pdf'),SCRATCH/'pdf_downloads'/(s['id']+'.pdf')]
    found=next((p for p in candidates if p.exists()),None)
    if found:
        target=PUB/'Attachments'/found.name;shutil.copy2(found,target)
        from pypdf import PdfReader
        pages=len(PdfReader(str(target)).pages)
        rec=dict(id=s['id'],url=s.get('pdf_url'),file='Attachments/'+found.name,sha256=sha(target),bytes=target.stat().st_size,page_count=pages,status='DOWNLOADED_AND_PARSED')
        download_records.append(rec);s['attachment']=rec
    elif s.get('local_existing_path'):
        p=Path(s['local_existing_path']);assert p.is_file()
        s['existing_attachment']=dict(vault_path=p.relative_to(VAULT).as_posix(),sha256=sha(p),bytes=p.stat().st_size,page_count=s['page_count'])

stats=dict(source_records=len(sources),distinct_document_keys=len({s['canonical_document_key'] for s in sources}),
    by_batch=dict(Counter(s['batch'] for s in sources)),by_reading_level=dict(Counter(s['reading_level'] for s in sources)),
    by_library_relation=dict(Counter(s['library_relation'] for s in sources)),downloaded_pdfs=len(download_records),
    downloaded_pdf_pages=sum(d['page_count'] for d in download_records),downloaded_bytes=sum(d['bytes'] for d in download_records),
    existing_local_pdfs=sum('existing_attachment' in s for s in sources),
    countries_and_regions=sorted({c for s in sources for c in s['countries']}),legacy_records=len(old))
corpus=dict(schema_version='1.0',task_id='BRD-055',intake_id='RND-20260923-1472cd05',compiled_on=DATE,
    purpose_vi='Kho nghiên cứu quốc tế cho SAGE-EvoBridge; người dùng hoãn sáng chế và yêu cầu thu thập dữ liệu.',
    evidence_policy='UNVERIFIED_REFERENCE; reading depth is not validation; no runtime rule or engineering approval.',
    counting_policy_vi='Hồ sơ là trang/tài liệu có định vị đọc. AI-018 và GE-019 thuộc cùng bộ IFC. TCVN nhận diện theo từng phần. Không khẳng định các nguồn chưa khớp chính xác đều là tài liệu hoàn toàn mới.',
    prior_index=dict(path='research/literature/index.json',sha256=sha(REPO/'research/literature/index.json'),records=len(old),previous_reading_status_not_refreshed=True),
    stats=stats,sources=sources)
dump(ROOT/'corpus.json',corpus);dump(PUB/'Data/corpus.json',corpus);dump(PUB/'Data/downloads.json',download_records)
events=[]
if (SCRATCH/'pdf_download_log.json').exists():
    events.append(json.loads((SCRATCH/'pdf_download_log.json').read_text(encoding='utf-8')))
events.append({'batch':'root-standards','completed_ids':['ST-002','ST-004','ST-006'],
    'interrupted_ids':['ST-005','ST-011','ST-013'],
    'note':'Stopped the remaining slow downloads; no completed local PDF claimed for interrupted items.'})
dump(PUB/'Data/acquisition_events.json',events)
(PUB/'Data/sources.jsonl').write_text(''.join(json.dumps(s,ensure_ascii=False)+'\n' for s in sources),encoding='utf-8')

for s in sources:
    scalar=lambda x: "'"+str(x).replace("'","''")+"'"
    front='\n'.join(f'{k}: {scalar(v)}' for k,v in dict(id=s['id'],title=s['title'],source_url=s['url'],accessed_on=DATE,reading_level=s['reading_level'],evidence_status='UNVERIFIED_REFERENCE',claim_ceiling='IDEA',type=s['source_type']).items())
    text=f'---\n{front}\ntags: [sage-evobridge, research, reference]\n---\n\n# {s["title"]}\n\n'
    text+=f'[Nguồn gốc]({s["url"]}) · {s["publisher"]} · Năm: {s["year"] if s["year"] is not None else "chưa xác minh/không ghi"}.\n\n'
    if s['authors']:text+='Tác giả/cơ quan: '+', '.join(s['authors'])+'.\n\n'
    if s.get('doi'):text+=f'DOI: [{s["doi"]}](https://doi.org/{s["doi"]}).\n\n'
    text+=f'**Mức đọc:** {READING[s["reading_level"]]}. **Truy cập:** {s["access_status"]}.\n\n**Vị trí đã đọc:** {s["read_locator"]}\n\n'
    text+='## Nội dung rút ra\n\n'+s['summary_vi']+'\n\n'+'\n'.join('- '+x for x in s['key_points_vi'])+'\n\n'
    text+='## Giới hạn\n\n'+'\n'.join('- '+x for x in s['limitations_vi'])+'\n\n'
    text+='## Liên hệ dự án — diễn giải của nhóm nghiên cứu\n\n'+s['project_use_vi']+'\n\n'
    if s.get('edition_status'):text+='**Phiên bản:** '+s['edition_status']+'\n\n'
    if s.get('attachment'):text+='Bản PDF đã lưu: '+wik(s['attachment']['file'],s['id']+'.pdf')+f' ({s["attachment"]["page_count"]} trang; số trang không đồng nghĩa số trang đã đọc).\n\n'
    elif s.get('existing_attachment'):text+='Bản có sẵn: [['+s['existing_attachment']['vault_path']+f'#page={s["read_locator"].split("PDF trang ")[-1].split(" ")[0]}|PDF trong thư viện TCVN]].\n\n'
    elif s.get('pdf_url'):text+=f'[Liên kết PDF ngoài vault]({s["pdf_url"]}) — chưa lưu bản cục bộ.\n\n'
    if s['related_urls']:text+='Liên kết bổ sung (không tự động tính là đã đọc):\n\n'+'\n'.join(f'- [Nguồn liên quan {i+1}]({u})' for i,u in enumerate(s['related_urls']))+'\n\n'
    if s['legacy_matches']:text+='Đối chiếu kho cũ: '+', '.join(m['id']+' ('+m['basis']+')' for m in s['legacy_matches'])+'.\n\n'
    text+='Nội dung là ghi chú tham khảo. Quyền sử dụng toàn văn/huấn luyện chưa được xác nhận; '+('chỉ lưu thư mục AASHTO.' if s['id']=='ST-001' else 'không phải quy tắc thiết kế đã phê duyệt.')+'\n\n'
    text+=wik(INDEX,'Về thư viện')+' · '+wik('07 - Du lieu va quyen su dung','Quy ước dữ liệu')+'\n'
    (PUB/'Sources'/(s['id']+'.md')).write_text(text,encoding='utf-8')

groups=[
('01 - Tieu chuan va pham vi ap dung','Tiêu chuẩn và phạm vi áp dụng',[s for s in sources if s['id'].startswith('ST-')],
 'Tiêu chuẩn quốc gia, sổ tay chủ quản, Model Code, phương pháp thử và thông báo sửa đổi được giữ thành các loại nguồn khác nhau. Không gộp hệ số hoặc tải xe giữa quốc gia chỉ vì cùng tên LRFD.'),
('02 - Dang cau va cong trinh the gioi','Dạng cầu và công trình thế giới',[s for s in sources if s['id'].startswith('BM-') and (int(s['id'][3:])<=12 or int(s['id'][3:])>=27)]+[byid['GE-014'],byid['GE-016']],
 'Các hồ sơ công trình phục vụ nhận diện hệ chịu lực, bối cảnh và quá trình phát triển. Phân biệt cầu bộ hành thử nghiệm, kết cấu triển lãm và cầu đường bộ. Một trang dự án chưa đủ dựng lại mô hình tính.'),
('03 - Vat lieu che tao va hu hong','Vật liệu, chế tạo và hư hỏng',[s for s in sources if s['id'].startswith('BM-') and 13<=int(s['id'][3:])<=26]+[byid['ST-008'],byid['ST-010'],byid['ST-016'],byid['ST-017'],byid['BM-027']],
 'Lưu quy trình chế tạo, đặc tính đo được, mô hình vật liệu, dạng liên kết và cơ chế hư hỏng riêng. Các tuyên bố ưu việt hoặc giảm carbon của một case chưa trở thành quy luật phổ quát.'),
('04 - Hinh hoc co hoc va tim hinh','Hình học, cơ học và tìm hình',[s for s in sources if s['id'].startswith('GE-')],
 'Đồ thị nút–thanh, miền mật độ, mặt ẩn và mesh là các cách biểu diễn khác nhau. Tìm hình cân bằng, tối ưu phân bố vật liệu và dựng bề mặt phục vụ những bài toán khác nhau; cần giữ giả thiết của từng nguồn.'),
('05 - AI xay dung va bo du lieu','AI xây dựng và bộ dữ liệu',[s for s in sources if s['id'].startswith('AI-')]+[byid['BM-029']],
 'Phân biệt công cụ đề xuất, phương pháp lựa chọn mẫu, bộ đo đạc hiện trường và tập hình CAD. Chưa tải toàn bộ các dataset lớn, chưa tái lập bài báo, chưa huấn luyện AI. Trang dataset là đầu mối truy cập có nguồn.'),
]
for name,title,ss,intro in groups:
    t=f'# {title}\n\n{intro}\n\n| Hồ sơ | Mức đọc | Quốc gia/phạm vi |\n|---|---|---|\n'
    for s in ss:t+=f'| {ref(s,True)} | {READING[s["reading_level"]]} | {", ".join(s["countries"]) or "chưa xác minh"} |\n'
    md(name,t+'\n'+wik(INDEX,'Về thư viện'))

md('06 - Ban do tri thuc cho dam gian',f'''# Bản đồ tri thức cho dầm/giàn chịu uốn

Đây là cách tổ chức tài liệu đã thu thập để đọc và tra cứu. Chưa triển khai bộ sinh cấu kiện hoặc chạy sáng chế.

| Mảnh tri thức | Cần ghi lại từ nguồn | Tài liệu khởi đầu |
|---|---|---|
| Hệ chịu lực | Nút, thanh, nhịp, gối; kéo/nén/uốn và phạm vi giả thiết | {refs(['ST-104','ST-106','GE-006']).replace('|','\\|')} |
| Mặt cắt và vật liệu | Hình học, mô hình vật liệu, thí nghiệm và đơn vị | {refs(['BM-018','ST-016','ST-017']).replace('|','\\|')} |
| Liên kết | Truyền lực, độ cứng, cấu tạo, dạng phá hoại | {refs(['BM-014','BM-020']).replace('|','\\|')} |
| Hình học liên tục | Miền thiết kế, độ phân giải, tính liên thông và bề dày | {refs(['GE-003','GE-004','GE-007']).replace('|','\\|')} |
| Chế tạo | Hướng in, dị hướng, đúc, vận chuyển, lắp dựng | {refs(['GE-012','GE-014','GE-022','ST-010']).replace('|','\\|')} |
| Dữ liệu BIM | Hình học, ngữ nghĩa và quan hệ cấu kiện | {refs(['AI-018','AI-019','GE-019','GE-020']).replace('|','\\|')} |
| Đánh giá và tìm kiếm | Mục tiêu, đa dạng, ngân sách và bất định | {refs(['AI-001','AI-003','AI-005','AI-006']).replace('|','\\|')} |
| Phản hồi thực tế | Quan trắc, môi trường và kết quả can thiệp | {refs(['AI-016','AI-017','BM-025']).replace('|','\\|')} |

## Những phân biệt cần giữ

TNA xử lý tìm hình nén trong giả thiết cụ thể; không thay cho mọi dầm chịu uốn. Marching Cubes trích bề mặt từ trường vô hướng; bản thân thao tác ấy không đo sức chịu tải. {refs(['GE-002','GE-007'])}

Một bộ cấu kiện có hình hữu cơ cần thêm thông tin vật liệu, liên kết, trạng thái thi công và kết quả thực nghiệm. Case dầm in bê tông là đầu mối đọc tiếp; chưa có đủ toàn văn để tái lập trong dự án. {refs(['GE-014','GE-015'])}

Quality-diversity và tối ưu Pareto giúp đặt hai câu hỏi khác nhau về sự đa dạng và đánh đổi. Mô hình thay thế dự đoán kết quả; phải giữ tách biệt với đánh giá thực. {refs(['AI-001','AI-003','AI-006'])}

Thư viện hiện tại là nền nghiên cứu có truy xuất nguồn, chưa đủ để xác nhận tính mới của phát minh hay sự phù hợp thiết kế cầu.

{wik(INDEX,'Về thư viện')}
''')

md('07 - Du lieu va quyen su dung',f'''# Quy ước dữ liệu và quyền sử dụng

Mỗi hồ sơ có ID, tiêu đề, cơ quan/tác giả, năm nếu xác minh được, URL gốc, DOI nếu có, quốc gia/phạm vi, chủ đề, mức truy cập, mức đọc, vị trí đọc, tóm tắt, giới hạn và liên hệ dự án. Mọi hồ sơ giữ `UNVERIFIED_REFERENCE`, trần `IDEA`; không có quy tắc nào tự động được đưa vào bộ tính.

| Trạng thái | Ý nghĩa |
|---|---|
| SELECTED_SECTIONS_READ | Đã đọc các phần được chỉ rõ; không có nghĩa đọc hết tài liệu |
| ABSTRACT_READ | Chỉ đọc tóm tắt; kết quả và phương pháp chưa đối chiếu toàn văn |
| OFFICIAL_PAGE_READ | Đọc trang cơ quan, dự án hoặc tài liệu phần mềm |
| METADATA_ONLY | Thư mục/chỉ mục; không dùng suy ra nội dung kỹ thuật |
| BLOCKED | Lần mở trực tiếp thất bại; vị trí đọc nói rõ nếu chỉ có chỉ mục |

Tệp PDF tải thành công được kiểm chữ ký, parse số trang và băm SHA-256. Số trang là quy mô tài liệu đã lưu, không phải khối lượng đã đọc. Các bản TCVN có sẵn được liên kết tại chỗ; không tạo thêm bản sao.

Đầu ra có [corpus JSON](Data/corpus.json), [từng hồ sơ JSONL](Data/sources.jsonl) và [sổ tệp tải](Data/downloads.json). Mã xây gói chỉ phục vụ tổ chức tài liệu, không phải thuật toán sáng chế.

## Khi bổ sung Family Revit sau này

Một hồ sơ Family nên có nguồn và quyền sử dụng; tên/phiên bản Revit; loại cấu kiện; tham số và đơn vị; hệ trục; hình học; vật liệu; kiểu liên kết; bản vẽ/tính toán liên quan; giới hạn áp dụng. Đợt này chưa trích xuất hoặc gắn nhãn bất kỳ Family nào.

Chưa xây tập dữ liệu huấn luyện. Quyền đọc/tải không tự động bao gồm tái phân phối, thu nạp toàn văn hoặc huấn luyện mô hình. Với tiêu chuẩn trả phí, giữ thư mục và liên kết; riêng AASHTO được gắn cờ hạn chế dùng với AI theo thông báo của nhà xuất bản. {refs(['ST-001'])}

## Liên hệ kho hiện có

Đã đối chiếu với {len(old)} hồ sơ trong chỉ mục cũ theo DOI, tiêu đề chuẩn hóa hoặc URL. Các trường chưa khớp chính xác chỉ được ghi là chưa tìm thấy khớp; không khẳng định đều là tài liệu mới hoàn toàn. Những đánh giá nội dung của kho cũ không được tự động kế thừa vào bộ mới.

Quốc gia trong ghi chú phản ánh phạm vi nguồn, nơi công trình hoặc cơ quan tác giả đã xác minh; không phải quốc tịch tác giả. `European Union` và `International` không được tính là quốc gia.

{wik(INDEX,'Về thư viện')}
''')

gaps=[]
for data in batches.values():
    for x in data.get('gaps_vi',[]):
        if x not in gaps:gaps.append(x)
md('08 - Khoang trong va danh muc doc tiep',f'''# Khoảng trống và danh mục đọc tiếp

Độ phủ tăng không thay thế độ sâu và dữ liệu thực nghiệm. Các mục dưới đây là công việc nghiên cứu còn thiếu, chưa được đánh dấu hoàn thành.

| Ưu tiên | Dữ liệu cần bổ sung | Điều kiện để dùng được |
|---|---|---|
| P0 | Family Revit thật của người dùng và bản vẽ/tính toán đi kèm | Có quyền sử dụng, đơn vị, tham số và phạm vi rõ |
| P0 | Bộ tiêu chuẩn áp dụng của dự án | Đúng phiên bản, phụ lục, đính chính, điều khoản được người có chuyên môn đối chiếu |
| P0 | Thí nghiệm dầm/giàn, mối nối và mỏi | Tải/gối/vật liệu/hình học, sai số đo và dạng phá hoại đủ tái lập |
| P1 | Dầm tối ưu/in 3D và dữ liệu chế tạo | Đọc toàn văn; có thông tin dị hướng, dung sai, liên kết, thí nghiệm |
| P1 | Dataset và mã gốc bài AI | Xem license, phiên bản, cách chia tập; tái lập baseline |
| P1 | Sự cố và kết quả sửa chữa | Đọc đủ các phần điều tra và phân biệt giả thuyết với kết luận |
| P2 | Tiêu chuẩn/case Hàn Quốc, Nam Mỹ, châu Phi | Mở rộng nguồn kỹ thuật ngoài các trang dự án tổng quan |
| P2 | Carbon, giá thành, logistics địa phương | Cùng ranh giới vòng đời, năm và vùng áp dụng |

Đọc tiếp phần 2 điều tra Tretten tại [NSIA](https://nsia.no/Road/Published-reports/2024-03). Phần này đã phát hành; đợt hiện tại mới đọc phần 1.

## Khoảng trống ghi nhận khi đọc từng nhóm

'''+ '\n'.join('- '+x for x in gaps)+f'\n\n{wik(INDEX,"Về thư viện")}')

rows='\n'.join(f'| {READING[k]} | {v} |' for k,v in stats['by_reading_level'].items())
relation=stats['by_library_relation']
md(INDEX,f'''---
tags: [sage-evobridge, research, index]
compiled_on: '{DATE}'
evidence_status: UNVERIFIED_REFERENCE
---

# Thư viện nghiên cứu quốc tế SAGE-EvoBridge

**{stats['source_records']} hồ sơ nguồn có ghi chú tiếng Việt**, tổ chức theo tiêu chuẩn, dạng cầu, vật liệu–chế tạo, hình học–cơ học và AI. Thu thập để xây nền dữ liệu; chưa chạy sáng chế cấu kiện.

| Mức nghiên cứu | Số hồ sơ |
|---|---:|
{rows}

Đã lưu **{stats['downloaded_pdfs']} PDF** ({stats['downloaded_pdf_pages']} trang tài liệu; {stats['downloaded_bytes']/1048576:.1f} MiB) và liên kết **{stats['existing_local_pdfs']} PDF TCVN có sẵn**. Đây không phải số trang đã đọc. Trong 42 hồ sơ đọc một số phần, 12 phần TCVN mới đọc điều phạm vi; định vị chi tiết nằm tại từng ghi chú.

## Mở theo chủ đề

'''+ '\n'.join('- '+wik(name,title) for name,title,_,_ in groups)+f'''
- {wik('06 - Ban do tri thuc cho dam gian','Bản đồ tri thức cho dầm/giàn')}
- {wik('07 - Du lieu va quyen su dung','Dữ liệu, mức đọc và quyền sử dụng')}
- {wik('08 - Khoang trong va danh muc doc tiep','Khoảng trống và danh mục đọc tiếp')}

## Phạm vi quốc tế

Nguồn có liên hệ với: {', '.join(stats['countries_and_regions'])}. Độ sâu không đồng đều: có nghiên cứu đọc phần toàn văn, có hồ sơ công trình và có đầu mục chờ truy cập. Nam Phi được bổ sung qua Msikaba; Nam Mỹ qua Chacao và nghiên cứu danh mục cầu Brazil.

## Những mốc phiên bản cần chú ý

- Nhật: bản MLIT sửa đổi 2025, thiết kế mới áp dụng từ 01/04/2026. {refs(['ST-002'])}
- Eurocodes: cần kiểm tra thời điểm chuyển tiếp và phụ lục quốc gia. {refs(['ST-003','ST-015'])}
- Bản CD350 năm 2020 trong bộ này được đánh dấu **đã thay thế**. {refs(['ST-012'])}
- Tên nghiên cứu CSA S6:25 không có nghĩa báo cáo đó là toàn văn bộ tiêu chuẩn. {refs(['ST-013'])}

## Nối với thư viện cũ

Có **{relation.get('MATCHES_EXISTING_LIBRARY',0)} hồ sơ khớp kho cũ**, **{relation.get('EXISTING_LOCAL_STANDARD',0)} phần tiêu chuẩn có sẵn**, và **{relation.get('NO_EXACT_MATCH_IN_PRIOR_INDEX',0)} hồ sơ chưa thấy khớp chính xác trong chỉ mục đối chiếu**. Có {stats['distinct_document_keys']} khóa tài liệu phân biệt vì hai hồ sơ nghiên cứu các phần khác nhau của cùng bộ IFC. Không cộng thẳng các hồ sơ vào số tài liệu duy nhất của toàn vault.

[[DYLIGHT Bridge Evolution/Literature/00 Thu vien hoc thuat|Thư viện học thuật hiện có]] · [[DYLIGHT Bridge Evolution/Standards/TCVN 11823-2017/00 - TCVN 11823-2017|Bộ TCVN hiện có]]

Nguồn gốc, vị trí đọc, giới hạn và tệp PDF nằm trong từng hồ sơ. Không có nguồn nào ở đây được coi là thiết kế đã được phê duyệt hoặc bằng chứng cấu kiện mới đã an toàn.
''')

readme=f'''# BRD-055 — International research collection

Additive research corpus for the user's research-first request. Canonical intake RND-20260923-1472cd05. No invention algorithm, runtime solver, model training or recurring progress automation is implemented.

- {stats['source_records']} source records; {stats['distinct_document_keys']} document keys.
- Reading levels: {json.dumps(stats['by_reading_level'],ensure_ascii=False)}.
- Existing-library matches: {json.dumps(relation,ensure_ascii=False)}.
- Downloaded PDFs: {stats['downloaded_pdfs']}; existing local standards linked: {stats['existing_local_pdfs']}.
- Target: `{VAULT/COLLECTION}`.
- Staged index: [Open](<publication/{INDEX}.md>).

All source claims remain UNVERIFIED_REFERENCE / IDEA. No engineering verification or global novelty claim. Exact comparisons do not prove all unmatched references are globally new. The legacy 234-record index is unchanged; no previous reading status is promoted.

`source_batches` preserves reviewed input records; `corpus.json` and `publication/Data` contain the normalized output. `qa_report.json` records checks. Publication is additive with hash verification. Repository handoff acceptance covers documentation integrity only.
'''
(ROOT/'README.md').write_text(readme,encoding='utf-8')
dump(ROOT/'stats.json',stats)
print(json.dumps(stats,ensure_ascii=False,indent=2))
