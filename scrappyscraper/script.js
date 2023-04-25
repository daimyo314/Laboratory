// Load the Google Charts library
google.charts.load('current', {'packages': ['sankey']});
google.charts.setOnLoadCallback(fetchAndDrawData);

function fetchAndDrawData() {
    const url = "http://localhost:8086";
    const token = "HZgcXFC4W6bAy-D3bWuSoNs_gabsOCkfElPLQhxylDKhKunDe1ai86-udL2uKY4lQQT06RFqBqj9yO8hcWmgIg==";
    const org = "Scrappy";
    const bucket = "Scrappybucket2";
  
    const fluxQuery = `
      from(bucket: "${bucket}")
        |> range(start: -1h)
        |> filter(fn: (r) => r._measurement == "network_telemetry")
        |> join(
          on: ["dst_ip"],
          tables: {left: _result, right: 
            from(bucket: "${bucket}")
              |> range(start: -1h)
              |> filter(fn: (r) => r._measurement == "whois_data")
          }
        )
        |> group(columns: ["src_ip", "owner"])
        |> count(column: "_value")
        |> map(fn: (r) => ({src_ip: r.src_ip, owner: r.owner, count: r._value}))
    `;
    
    const requestOptions = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/vnd.flux',
        'Authorization': `Token ${token}`
      },
      body: fluxQuery
    };
  
    fetch(`${url}/api/v2/query?org=${org}`, requestOptions)
      .then(response => {
        if (!response.ok) {
          throw new Error('Error fetching data from InfluxDB');
        }
        return response.json();
      })
      .then(data => {
        const rows = processData(data);
        drawSankey(rows);
      })
      .catch(error => {
        console.error('Error:', error);
      });
  }  

  function processData(responseData) {
    const rows = [];
  
    const table = responseData.tables[0];
    if (!table) {
      return rows;
    }
  
    table.records.forEach(record => {
      rows.push([record.src_ip, record.owner, record.count]);
    });
  
    return rows;
  }  

function drawSankey(rows) {
  const data = new google.visualization.DataTable();
  data.addColumn('string', 'Source');
  data.addColumn('string', 'Destination');
  data.addColumn('number', 'Count');
  data.addRows(rows);

  const options = {
    width: 800,
    height: 600
  };

  const chart = new google.visualization.Sankey(document.getElementById('sankey_diagram'));
  chart.draw(data, options);
}

// Refresh data and redraw the Sankey diagram every 30 seconds
setInterval(fetchAndDrawData, 30000);