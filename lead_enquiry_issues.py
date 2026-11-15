found some issues in code


1. there are 2 fields in Quotation - validity_days & estimated_turnaround_days. 
Explain difference in both. 
while submit quotation getting error for validity_days as not submitting via form

2. When its won for one lab, automatically should be declined for others


Add New functionality -

1. after won by customer lab will click on accept & Create order. Then entry will be an order. Previously communication was on quotation's respect now from here further communication will be in order's respect. 
2. Document will be uploaded here. In order there will be a provision of upload invoice. Order status in-progress untill not marked as complete.
3. Finally mark as completed by done either by lab or customer. If customer marks it complete then it should be complete directly. If lab mark it complete then it will go to customer for accept or decline.
4. One more tab will be - In dispute. Both Lab and customer will have a button - Raise Dispute. when status In Dispute then Labfinder Team will come in picture to check the communication history of lab and customer and will take decision on it to fix the dispute in between both. Separate tab for dispute.
5. Three separate tabs - Lead, Orders, Dispute
6. In customer dashboard show separate tab for orders. Here he can check proper communication and upload the invoice. There will be communication window between Lab and customer.
7. One more section in customer dashboard for Review. He can see his reviews for each lab




in lead enquiry discussion - attachment option not coming at customer end

quote_form = QuotationForm(request.POST) - here Estimated turnaround days not saving in database

No tab for declined enquiries in lead enquiry page at customer end

# in customer dashboard where all lead visible to him under Laboratory Responses make bold those labs where response came form lab. That is unread messa    





On the Send Enquiry page when customer clicks on Linked Login then login will be via linkedin (functionality already working in project)



If click on Sign in then a popup will be opened. Check the attached first screenshot.



When customer has no account, he will click on signup in popup then another popup will be opened. Check the 2nd screenshot for the exact design reference. 



After that 3rd screenshot for OTP verification



After OTP verification, the complete profile popup will be opened. Check the 4th screenshot.

Update the existing login/signup code to be the same as this.

We have already created a common popup.

Use and update that or create just a new functionality. but should be common for each screen login/signup/linkedin login of customer section  



update below code to create profile instance and save phone in customer profile. Currently phone is not saving in customer profile.
def account_api_signup(request):
    