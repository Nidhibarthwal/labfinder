






Make below section responsive - [_lp_header_nav.html#L4-38](fileLineRange;file:///Users/nidhikotiyal/django_projects/labfinder/templates/accounts/includes/_lp_header_nav.html#L4-38) 

[_lp_orders.html#L47-56](fileLineRange;file:///Users/nidhikotiyal/django_projects/labfinder/templates/accounts/includes/_lp_orders.html#L47-56) 

[order_detail.html#L56-747](fileLineRange;file:///Users/nidhikotiyal/django_projects/labfinder/templates/enquiries/order_detail.html#L56-747) 
                              
                    
                                    
                            
lab dashboard - Edit profile
when clicks on search 50+ discipline, the discipline that alreadyy selected should be selected in <div id="disciplinesSuggestionsList"></div>
same implement to type of testing, category, subcategory also
take refrence from <input type="text" id="disciplinesSearchInput" class="review-ta





There will be 3 plans for lab to purchase for promotion
reference (figma-screens/promotional-packages.png)
1. Basic (Free)	
2. Verified Lab (Growth)	
3. Trusted Partner (Pro)

Simillarly some Add on
reference (figma-screens/promotional-addon.png)

create db structure for these in lab/models.py

workflow will be like this -
If any lab purchase Verified Lab (Growth) plan, a form will open to that lab where fields will be like
price will be there to diaply and pay in last
Priority Tier 2 - will be visible in form
lab has to Verified Lab Badge by filling (GST/License)
option in insert 1 Static Header Banner.
Other information (in figma screen) will be there to provide details of package to lab before purchase.

Same will be for plan - Trusted Partner (Pro) (excel column D)
Price and Priority Tier 1 (Top Organic) - to display the lab
lab has to verify NABL / ISO details and Verified Highlight Badge will be with lab name or logo
option to insert Carousel Banner (Up to 3) + Video
Send Enquiry, Direct Phone, WhatsApp & Instant RFQ option will be at customer end
Lab Can hide reviews with this plan
lab will have Hidden (Ad-free profile) etc



Packages features can be add by add more from admin panel from super user

