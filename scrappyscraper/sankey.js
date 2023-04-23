const url = "http://localhost:5000/data";

function fetchData() {
    fetch("http://localhost:5000/api/data")
      .then((response) => response.json())
      .then((data) => {
        drawSankey(data);
      })
      .catch((error) => {
        console.error("Error fetching data:", error);
      });
  }

function drawSankey(data) {
  d3.select("svg").remove();

  var margin = { top: 10, right: 10, bottom: 10, left: 10 },
    width = 700 - margin.left - margin.right,
    height = 600 - margin.top - margin.bottom;

  var svg = d3
    .select("#sankey")
    .append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom)
    .append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

  var sankey = d3
    .sankey()
    .nodeWidth(15)
    .nodePadding(10)
    .size([width, height]);

  sankey
    .nodes(data.nodes)
    .links(data.links)
    .layout(32);

  var link = svg
    .append("g")
    .selectAll(".link")
    .data(data.links)
    .enter()
    .append("path")
    .attr("class", "link")
    .attr("d", sankey.link())
    .style("stroke-width", function (d) {
      return Math.max(1, d.dy);
    })
    .sort(function (a, b) {
      return b.dy - a.dy;
    });

  var node = svg
    .append("g")
    .selectAll(".node")
    .data(data.nodes)
    .enter()
    .append("g")
    .attr("class", "node")
    .attr("transform", function (d) {
      return "translate(" + d.x + "," + d.y + ")";
    });

  node
    .append("rect")
    .attr("height", function (d) {
      return d.dy;
    })
    .attr("width", sankey.nodeWidth())
    .style("fill", function (d) {
      return (d.color = d3.scale.category20c()(d.name.replace(/ .*/, "")));
    });

  node
    .append("text")
    .attr("x", -6)
    .attr("y", function (d) {
      return d.dy / 2;
    })
    .attr("dy", ".35em")
    .attr("text-anchor", "end")
    .attr("transform", null)
    .text(function (d) {
      return d.name;
    })
    .filter(function (d) {
      return d.x < width / 2;
    })
    .attr("x", 6 + sankey.nodeWidth())
    .attr("text-anchor", "start");
}

fetchData();
setInterval(fetchData, 30000);