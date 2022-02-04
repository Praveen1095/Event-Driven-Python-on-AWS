import pandas

def transform(ny_url,jh_url):
    ny_data = pandas.read_csv(ny_url)
    ny_data = ny_data.fillna(0)
    ny_data = ny_data.astype({"date":'datetime64[ns]'})

    jh_data = pandas.read_csv(jh_url)
    jh_data = jh_data.fillna(0)
    jh_data = jh_data[["Date", "Country/Region", "Recovered"]]
    jh_data["Country/Region"] = "US"
    jh_data = jh_data.astype({"Date":'datetime64[ns]', "Recovered": 'int64'})
    jh_data = jh_data[["Date", "Recovered"]]
    jh_data.rename(columns={"Date": 'date',"Recovered":'recovered'}, inplace=True)
    
    combined_data = pandas.merge(ny_data,jh_data , on= 'date')
    return combined_data
    # print(combined_data.tail(5))
 
    
    
    




# transform(ny_url,jh_url)