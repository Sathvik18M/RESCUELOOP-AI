"""Add isolated, explicitly synthetic presentation conversations. Never sends messages."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlsplit
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/backend'))
from app.domain.support_issues import ISSUES

# Prepared examples, not statements about live orders or completed operations.
STORIES = {
'01': ('The payment reference is PAY4821. I paid Rs 799 this morning.', 'I have captured your payment reference and amount. The store team needs to match the payment with checkout records before confirming an order. Please do not pay again.'),
'02': ('The order shows a speaker, but I selected wireless headphones.', 'I have recorded both products. The store will verify the checkout record and available stock before offering a correction. No order changes will happen without your confirmation.'),
'03': ('It has not shipped. Please cancel the order.', 'The cancellation policy allows review before shipping. I have prepared the cancellation request for confirmation; any refund will follow the original payment record and merchant rules.'),
'04': ('I ordered medium. Could I change it to large?', 'I have saved medium as the current size and large as the requested size. The team will check stock and dispatch status before quoting any difference.'),
'05': ('Please keep the first order and cancel the second one.', 'I have recorded which order you want to keep. The store will compare both payment and fulfillment records before asking you to confirm cancellation of the duplicate.'),
'06': ('The expected date was yesterday, and tracking has not moved.', 'I have recorded the missed delivery date. The team will check the latest courier event and request an updated estimate. I cannot promise a new date without courier confirmation.'),
'07': ('The correct landmark is the library beside the main gate.', 'I have saved the landmark. A new attempt requires a verified failed-delivery event and your confirmation of the proposed delivery details.'),
'08': ('The apartment should be 402, not 204.', 'I have captured the exact correction. The team must confirm whether the parcel can still be redirected before changing the delivery address.'),
'09': ('Tracking says delivered, but nobody at home received it.', 'I have recorded a delivery dispute. The team needs courier proof of delivery, the drop-off location and any recipient signature. The delivered scan alone does not resolve your complaint.'),
'10': ('Tomorrow afternoon would work best.', 'I have recorded your preferred time. The courier must confirm availability before a new delivery appointment can be offered.'),
'11': ('I can collect it from the shop tomorrow at 4 pm.', 'I have recorded your pickup preference. The seller must approve pickup and verify stock and slot availability. Collection requires a valid confirmation code.'),
'12': ('It says delivered, but the previous event says the attempt failed.', 'Those two shipment states conflict. I have preserved both events for seller verification and requested proof of delivery rather than treating the delivered status as conclusive.'),
'13': ('The headphones arrived with a broken headband. I have attached a picture.', 'I have recorded the broken headband and your attachment. Visible damage needs seller verification, and return eligibility depends on the delivery date. Please keep the packaging while the team reviews replacement options.'),
'14': ('The device will not switch on even after charging it.', 'I have captured the power failure and the charging step you already tried. The team will review defect eligibility; I will not ask you to repeat the same troubleshooting.'),
'15': ('I ordered black wireless headphones but received a blue Bluetooth speaker. I want a replacement.', 'I have saved the ordered item, received item and replacement request. The store must verify the order and delivery evidence, then check replacement policy and stock. Your case needs verification; please keep the received item and packaging.'),
'16': ('The charging cable is missing, but the headphones are present.', 'I have recorded exactly which item is missing. The team will compare the packing list with your order before proposing a missing-item shipment or another remedy.'),
'17': ('The stitching is coming apart after one use.', 'I have recorded the quality issue. The team needs to assess whether it is a defect covered by store policy before proposing a return or replacement.'),
'18': ('The listing showed metal, but the product I received is plastic.', 'I have saved the material mismatch. The seller will compare the listing with the received product and review eligibility. I have not assumed the product description was correct.'),
'19': ('It arrived three days ago and is damaged.', 'The stated delivery date is within the seven-day return window. Damage and order ownership still need verification. After eligibility is confirmed, I will present return terms and request your explicit consent.'),
'20': ('I want a refund of Rs 799 for the defective item.', 'I have recorded the requested amount and reason. This exceeds the automatic refund limit, so seller approval and the required inspection are needed. No refund has been issued.'),
'21': ('The refund was approved five days ago, but I cannot see it.', 'I have recorded the delay. The team will check the refund transaction reference and provider status. Approval alone is not proof that money has reached your account.'),
'22': ('I expected Rs 800 but received only Rs 500.', 'I have recorded the expected amount, received amount and Rs 300 difference. The store must reconcile the original payment and refund ledger before deciding on an adjustment.'),
'23': ('The watch arrived damaged. I prefer a replacement.', 'I have recorded your preferred resolution. Replacement eligibility, evidence and available stock must be checked before the seller offers terms for your confirmation.'),
'24': ('The return pickup was scheduled for yesterday. Nobody came.', 'I have recorded the missed pickup. The team will check the courier pickup event and arrange a verified alternative. Your return request remains open.'),
'25': ('Rs 799 was deducted, but checkout did not create an order.', 'I have saved the amount and checkout issue. Please share the payment reference through support, not card details. The store must reconcile payment before confirming an order or refund.'),
'26': ('Two charges of Rs 799 appear for one order.', 'I have recorded both charges as a payment dispute. The store will compare the transaction references before deciding whether one is a duplicate. No automatic refund has been initiated.'),
'27': ('The invoice includes an extra Rs 200.', 'I have recorded the disputed charge. The team will compare the agreed total, invoice and payment record, then explain or correct the difference after verification.'),
'28': ('Please issue the GST invoice in my business name.', 'I have recorded the invoice request. The store team can verify the billing details and provide the appropriate invoice. Please do not share payment-card information.'),
'29': ('Please engrave AARAV on the wallet, in block letters.', 'I have saved the exact engraving text and style. This product needs a verified draft order and seller approval before a customization request can be created. No request has been created prematurely.'),
'30': ('I requested AARAV, but the gift says ARAV.', 'I have saved both the requested spelling and the received spelling. The seller will compare the approved customization terms with the item and propose a correction.'),
'31': ('Gift wrapping was paid for but was not included.', 'I have recorded the missing paid customization. The store will verify the order add-on and packaging evidence before proposing a remedy.'),
'32': ('My engraved wallet is still not ready after the quoted preparation period.', 'I have saved the original preparation expectation. The seller must check the customization stage and provide an updated estimate; I cannot invent a completion date.'),
'33': ('The product stopped working after two months.', 'I have recorded the fault and purchase period. The team will verify the order and warranty terms before explaining the available repair or replacement process.'),
'34': ('Your first solution did not help. The second solution also did not resolve it.', 'Two unsuccessful resolution attempts require escalation. The complete history is available to the seller, and automated replies are paused until the store resumes AI assistance.'),
'35': ('Please let a person handle this conversation.', 'I have transferred the conversation to the store team. Automated replies are paused, and the full conversation remains available to the seller.'),
}
NAMES = ['Ananya Rao','Rohan Mehta','Priya Shah','Karthik Iyer','Neha Kapoor','Arjun Nair','Meera Joshi','Vikram Rao','Diya Patel','Rahul Das','Kavya Menon','Aditya Jain','Aarav Sharma','Isha Gupta','Sanjay Kumar','Nisha Rao','Varun Shah','Tara Singh','Dev Patel','Riya Nair','Aman Joshi','Pooja Das','Yash Mehta','Maya Iyer','Rohit Jain','Sneha Kapoor','Nitin Rao','Aditi Shah','Sana Mehta','Kabir Singh','Anika Nair','Dhruv Patel','Simran Das','Vivek Rao','Zoya Khan']

def lit(value):
    if value is None: return 'NULL'
    if isinstance(value, bool): return 'TRUE' if value else 'FALSE'
    return "'" + str(value).replace("'", "''") + "'"

def insert(table, row):
    return f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join(lit(v) for v in row.values())}) ON CONFLICT (id) DO NOTHING;"

def main():
    env=dotenv_values(ROOT/'.env',interpolate=False)
    target=urlsplit(env['HOSTED_DATABASE_URL'].replace('postgresql+psycopg://','postgresql://',1))
    runtime=dict(os.environ,PGHOST=target.hostname,PGPORT=str(target.port or 5432),PGDATABASE=unquote(target.path.lstrip('/')),PGUSER=unquote(target.username),PGPASSWORD=unquote(target.password),PGSSLMODE='require',PGCONNECT_TIMEOUT='15')
    statements=["BEGIN; SET LOCAL statement_timeout='25s';", "DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM merchants WHERE id='SELLER001') THEN RAISE EXCEPTION 'Merchant missing'; END IF; END $$;", "DO $batch$ BEGIN"]
    # Same baseline and replayable IDs: reruns add nothing and never rewrite history.
    stamp=datetime.now(timezone.utc)-timedelta(hours=2)
    total=0
    for index,issue in enumerate(ISSUES):
        code=issue.code; cid='SHOWCASE-CUSTOMER-'+code; conv='SHOWCASE-CONVERSATION-'+code
        handoff=code in {'34','35'}
        statements.append(insert('customers',dict(id=cid,merchant_id='SELLER001',name=NAMES[index]+' · '+issue.name,phone=None,language='en')))
        statements.append(insert('conversations',dict(id=conv,merchant_id='SELLER001',customer_id=cid,order_id=None,handoff=handoff,channel='demo',messaging_provider='disabled',provider_recipient=None,last_inbound_at=stamp.isoformat(),context=json.dumps({'synthetic':True,'presentation_sample':True,'issue_code':code,'no_external_actions':True}))))
        details,answer=STORIES[code]
        messages=[('customer',issue.example),('assistant',issue.next_step),('customer',details),('assistant',answer)]
        if code=='29':
            messages += [('customer','The wallet is in my cart. Please prepare a draft for the seller to review.'),('seller','The requested engraving is supported. The quoted engraving charge is Rs 199, subject to the draft-order review and your confirmation.'),('assistant','Please review: engraving AARAV in block letters; additional charge Rs 199. A verified proposal reference is required before confirmation. Nothing is charged or changed without consent.'),('customer','Understood. I will review the proposal before confirming.')]
        elif code=='13':
            messages += [('seller','I can see where the headband is broken. Please retain the item and packaging for inspection. I will review replacement availability.'),('customer','Thank you. I have kept the packaging and would prefer a replacement.')]
        elif handoff:
            messages += [('seller','Hello, this is the store team. I have the earlier conversation and will handle the issue personally.'),('customer','Thank you. Please keep me updated.')]
        elif code in {'09','12','15','20','22'}:
            messages += [('seller','I am reviewing the recorded details and supporting evidence. I will provide the next step once verification is complete.'),('customer','Thank you. Please keep this request open until it is resolved.')]
        else:
            messages += [('customer','Thank you. Please proceed with the verification and let me know the next step.')]
        for n,(role,body) in enumerate(messages):
            mid=f'SHOWCASE-MESSAGE-{code}-{n+1}'
            statements.append(insert('messages',dict(id=mid,conversation_id=conv,role=role,body=body,status='sample',provider_id=None,created_at=(stamp+timedelta(minutes=index,seconds=n*25)).isoformat(),case_ids='[]',completes_case=False,processed=True)))
            total+=1
        statements.append(insert('audit_logs',dict(id='SHOWCASE-AUDIT-'+code,merchant_id='SELLER001',actor='presentation_fixture',action='presentation.sample_added',entity_id=conv,detail=json.dumps({'synthetic':True,'issue_code':code,'source':'scripts/add_judges_inbox.py','messages':len(messages),'provider_calls':0,'case_counters_changed':False}),created_at=datetime.now(timezone.utc).isoformat())))
    statements += ["END $batch$;", "SELECT json_build_object('sample_conversations',count(*)) FROM conversations WHERE id LIKE 'SHOWCASE-CONVERSATION-%';", "SELECT json_build_object('sample_messages',count(*)) FROM messages WHERE id LIKE 'SHOWCASE-MESSAGE-%';", "SELECT json_build_object('outbound_jobs',count(*)) FROM jobs WHERE payload->>'message_id' LIKE 'SHOWCASE-MESSAGE-%';",'COMMIT;']
    command=['docker','exec','-i']
    for key in ('PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD','PGSSLMODE','PGCONNECT_TIMEOUT'): command+=['-e',key]
    command+=['infra-postgres-1','psql','-X','-q','-t','-A','--no-password','--set','ON_ERROR_STOP=1']
    result=subprocess.run(command,input='\n'.join(statements),env=runtime,capture_output=True,text=True,encoding='utf-8',timeout=50)
    if result.returncode:
        print(json.dumps({'status':'not_committed','details_suppressed':True})); raise SystemExit(1)
    print(result.stdout.strip())

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'status':'failed','error_type':type(exc).__name__,'details_suppressed':True})); raise SystemExit(1)
