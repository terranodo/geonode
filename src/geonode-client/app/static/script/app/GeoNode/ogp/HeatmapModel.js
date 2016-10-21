Ext.namespace("GeoNode");

var heatmapParams = {
  facet : "true",
  "facet.heatmap" : "bbox",
  "facet.heatmap.format" : "ints2D",
  "facet.heatmap.distErrPct": "0.05",
  fq: [
    "area:[0 TO 400]",
    "!(area:1 AND max_x:0 AND max_y:0)"
  ],
  'facet.heatmap.geom': "",
  rows: 0
};

GeoNode.HeatmapModel = Ext.extend(Ext.util.Observable, {

  radiusAdjust: 1.1,

  global_layers: 0,

  constructor: function(config) {
    var self = this;
    Ext.apply(this, config);
    this.addEvents({
      fireSearch: true
    });
    this.addListener('fireSearch', function(propagateToSearchTable){
      this.handleHeatmap();

      // should this search trigger also the search table?
      if(propagateToSearchTable){
        this.searchTable.doSearch();
      }
    });

    this.bbox_widget.viewer.mapPanel.map.events.register('moveend', '', function(){
      self.fireEvent('fireSearch', true);
    });

    this.bbox_widget.viewer.mapPanel.map.events.register('mousemove',this.bbox_widget.viewer.mapPanel.map, function(event){
      self.processEvent(event);
    },true);

    this.WGS84ToMercator = this.bbox_widget.WGS84ToMercator;

    Ext.QuickTips.init();

    this.tooltip = new Ext.ToolTip({
        html: 'test',
        cls: 'ogp-tooltip',
        hideDelay: 0,
        showDelay: 0,
        width: 80
      });

    //get the number of global layers
    // $.ajax({
    //   url: GeoNode.solrBackend,
    //   jsonp: "json.wrf",
    //   dataType: "jsonp",
    //   data : {
    //     q: '*',
    //     fq: 'area:[401 TO *]',
    //     rows: 0,
    //     wt: 'json'
    //   },
    //   success: function(response){
    //     self.global_layers = response.response.numFound;
    //   }
    // });
  },

  handleHeatmap: function(){
    this.deleteHeatmapLayer();
    this.makeHeatmapLayer();
  },

  setQueryParameters: function(){
    var extent = this.bbox_widget.viewer.mapPanel.map.getExtent();
    var center = extent.getCenterLonLat().transform(new OpenLayers.Projection('EPSG:900913'), new OpenLayers.Projection('EPSG:4326'));
    if (extent){
      extent = extent.transform(new OpenLayers.Projection('EPSG:900913'), new OpenLayers.Projection('EPSG:4326'));
      var bbox = {
        minX: extent.left,
        maxX: extent.right,
        minY: extent.bottom,
        maxY: extent.top
      };
      GeoNode.solr.center = {
        centerX: center.lat,
        centerY: center.lon
      }
      var params = GeoNode.solr.getOgpSpatialQueryParams(bbox);
      GeoNode.queryTerms.intx = params.intx;
      GeoNode.queryTerms.bf = params.bf;
      heatmapParams['facet.heatmap.geom'] = params['facet.heatmap.geom'];
    }
  },

  initHeatmapLayer:function(){
    return new Heatmap.Layer("Heatmap");
  },

  makeHeatmapLayer: function(){
    var self = this;
    this.setQueryParameters();
    var params = $.extend({}, GeoNode.queryTerms, heatmapParams);
    params.fq = $.merge([],  GeoNode.queryTerms.fq);
    $.merge(params.fq, heatmapParams.fq);
    $.ajax({
      url: GeoNode.solrBackend,
      jsonp: "json.wrf",
      dataType: "jsonp",
      data : $.param(params, true),
      success: function(response){
        var facetCounts = response.facet_counts;
        if (facetCounts != null){
          //var heatmapObject = facetCounts.facet_heatmaps.bbox;
          var heatmapObject = self._solrResponseToObject(response);
          self.heatmapObject = heatmapObject;
          self.drawHeatmapOpenLayers(heatmapObject);
        }
      }
    });
  },
  _solrResponseToObject : function(data){
    // Solr object is array of name/value pairs, convert to hash
    heatmap = {};
    heatmapArray = data.facet_counts.facet_heatmaps['bbox'];
    jQuery.each(heatmapArray, function(index, value) {
        if ((index % 2) == 0) {
        heatmap[heatmapArray[index]] = heatmapArray[index + 1];
        }});
    return heatmap;
    },
  drawHeatmapOpenLayers: function(heatmapObject){

    var map = this.bbox_widget.viewer.mapPanel.map;

    if(!this.heatmapLayer){
      this.heatmapLayer = this.initHeatmapLayer();
    }

    var classifications = this.getClassifications(heatmapObject);
    this.renderHeatmap(heatmapObject, classifications);

    if(map.getLayersByName("Heatmap").length == 0){
      map.addLayer(this.heatmapLayer);
      map.setLayerIndex(this.heatmapLayer, 2);
    }else{
      this.heatmapLayer.redraw();
    }
  },
  renderHeatmap : function(facetHeatmap, classifications)
    {
    var self = this;
    var map = this.bbox_widget.viewer.mapPanel.map;
    var maxValue = classifications[classifications.length - 1]; 
    this.heatmapLayer.points = [];
    var colorGradient = this.getColorGradient(this.getColors(), classifications);
    this.heatmapLayer.setGradientStops(colorGradient);
    this.heatmapLayer.setOpacity(0.50);

    var extent = map.getExtent();
    var mapLowerLeft = new OpenLayers.LonLat(extent.left, extent.bottom);
    var mapUpperRight = new OpenLayers.LonLat(extent.right, extent.top);
    var geodeticProjection = new OpenLayers.Projection("EPSG:4326");
    var mapLowerLeftGeodetic = mapLowerLeft.transform(map.getProjectionObject(), geodeticProjection);
    var mapUpperRightGeodetic = mapUpperRight.transform(map.getProjectionObject(), geodeticProjection);

    // cells size is also used on mouse click to define item capture distance
    var heatmapCellSize = Math.ceil(this.getCellSize(facetHeatmap, map));
    var latitudeStepSize = (facetHeatmap.maxY - facetHeatmap.minY) / facetHeatmap.rows;
    var longitudeStepSize = (facetHeatmap.maxX - facetHeatmap.minX) / facetHeatmap.columns;
    var countsArray = facetHeatmap.counts_ints2D;

    // iterate over cell values and create heatmap items
    jQuery.each(countsArray, function(rowNumber, currentRow){
        if (currentRow == null) return;
        jQuery.each(currentRow, function(columnNumber, value){
        if (value == null || value <= 0) return;

        var latitude = facetHeatmap.minY + ((facetHeatmap.rows - rowNumber- 1) * latitudeStepSize) + (latitudeStepSize * .5); 
        var longitude = facetHeatmap.minX + (columnNumber * longitudeStepSize) + (longitudeStepSize * .5);
        var geodetic = new OpenLayers.LonLat(longitude, latitude); 
        if (geodetic.lat > mapUpperRightGeodetic.lat || geodetic.lat < mapLowerLeftGeodetic.lat
            || geodetic.lon > mapUpperRightGeodetic.lon || geodetic.lon < mapLowerLeftGeodetic.lon)
        {return};  // point not on map
        var transformed = geodetic.transform(geodeticProjection, map.getProjectionObject());
        var tmpValue = Math.min(classifications[classifications.length-1] / maxValue, value / maxValue);
        self.heatmapLayer.addSource(new Heatmap.Source(transformed, heatmapCellSize, tmpValue));
        })
    });
  },
  getRadiusFactor: function(){
      var factor = [1.6, 1.5, 2.6, 2.4, 2.2, 1.8, 2., 2., 2.];
      var zoomLevel = this.bbox_widget.viewer.mapPanel.map.getZoom();
      if (zoomLevel <1){
        return 1;
      };

      var index = zoomLevel - 1;
      if (index > factor.length - 1){
        return factor[factor.length - 1];
      }

      var value = factor[index];
      return value;
  },

  heatmapMinMax: function (heatmap, stepsLatitude, stepsLongitude){
    var max = -1;
    var min = Number.MAX_VALUE;
    for (var i = 0 ; i < stepsLatitude ; i++){
      var currentRow = heatmap[i];
      if (currentRow == null){heatmap[i] = currentRow = []};
      for (var j = 0 ; j < stepsLongitude ; j++){
        if (currentRow[j] == null){
          currentRow[j] = -1;
        }

        if (currentRow[j] > max){
          max = currentRow[j];
        }

        if (currentRow[j] < min && currentRow[j] > -1){
          min = currentRow[j];
        }
      }
    }
    return [min, max];
  },

  deleteHeatmapLayer: function(){
    var map = this.bbox_widget.viewer.mapPanel.map;
    var heatmaplayers = map.getLayersByName('Heatmap');
    if(heatmaplayers.length > 0){
      for(var i=0; i<heatmaplayers.length; i++){
        map.removeLayer(heatmaplayers[i]);
      }
    }
  },

  /**
    uses a Jenks algorithm with 5 classifications
    the library supports many more options
  */
  getClassifications : function(facetHeatmap)
  {
  var flatArray = [];
  var count = 0;
  var maxValue = 0;
  for (var i = 0; i < facetHeatmap.counts_ints2D.length; i++) 
  {
      if (facetHeatmap.counts_ints2D[i] != null)  // entire row can be null
      for (var j = 0 ; j < facetHeatmap.counts_ints2D[i].length ; j++)
          {
          var currentValue = facetHeatmap.counts_ints2D[i][j];
          if (currentValue != null) // && facetHeatmap.counts_ints2D[i][j] != 0)
              {
          var flatArray = flatArray.concat(currentValue);
          if (currentValue > maxValue) maxValue = currentValue;
          count++;
          
              }
      }
  };
  // jenks classification takes too long on lots of data
  // so we just sample larger data sets
  reducedArray = [];
  var period = Math.ceil(count / 300);
  period = Math.min(period, 6);
  if (period > 1)
  {
      for (i = 0 ; i < flatArray.length ; i = i + period)
      reducedArray.push(flatArray[i]);
      reducedArray.push(maxValue);  // make sure largest value gets in, doesn't matter much if duplicated
  }
  else
      reducedArray = flatArray;
  var series = new geostats(reducedArray);
  numberOfClassifications = this.getColors().length - 1;
  var classifications = series.getClassJenks(numberOfClassifications);

  var lastExtraZero = -1;
  for (var i = classifications.length - 1 ; i > 0 ; i--)
      if (classifications[i] == 0 && lastExtraZero == -1)
      lastExtraZero = i;
  if (lastExtraZero > 0)
      classifications = classifications.slice(lastExtraZero)
  return classifications;
  },
  cleanupClassifications: function(classifications){
    // classifications with multiple 0 can cause problems
    var lastZero = classifications.lastIndexOf(0);
    if (lastZero == -1){
      return classifications;
    };
    classifications = classifications.slice(lastZero, classifications.length);
    return classifications;
  },

  getCellSize: function(facetHeatmap, map)
  {
  var mapSize = map.getSize();
  var widthInPixels = mapSize.w;
  var heightInPixels = mapSize.h;
  var heatmapRows = facetHeatmap.rows;
  var heatmapColumns = facetHeatmap.columns;
  var sizeX = widthInPixels / heatmapColumns;
  var sizeY = heightInPixels / heatmapRows;
  var size = Math.max(sizeX, sizeY);
  return size; 
  },

  getColors: function(){
    return [0x00000000, 0x0000dfff, 0x00effeff, 0x00ff42ff, 0xfeec30ff, 0xff5f00ff, 0xff0000ff];
  },

  /*
    convert Jenks classifications to Brewer colors
  */
   getColorGradient: function(colors, classifications)
    {
    colorGradient = {};
    maxValue = classifications[classifications.length - 1];
    if (classifications.length != colors.length)
        console.log("!!! number of classifications do not match colors", classifications.length, colors.length);
    for (var i = 0 ; i < classifications.length ; i++)
    {
        value = classifications[i];
        scaledValue = value / maxValue;
        scaledValue = Number(scaledValue.toFixed(4));
        if (scaledValue < 0)
        scaledValue = 0;
        colorGradient[scaledValue] = colors[i];
    }
    return colorGradient;
    },

  getCountGeodetic: function(heatmapObject, latitude, longitude){
      if (heatmapObject == null)
        return;
      var minimumLatitude = heatmapObject.minY;
      var maximumLatitude = heatmapObject.maxY;
      var deltaLatitude = maximumLatitude - minimumLatitude;
      var minimumLongitude = heatmapObject.minX;
      var maximumLongitude = heatmapObject.maxX;
      var deltaLongitude = maximumLongitude - minimumLongitude;

      var stepsLatitude = heatmapObject.rows;
      var stepsLongitude = heatmapObject.columns;
      var stepSizeLatitude = deltaLatitude / stepsLatitude;
      var stepSizeLongitude = deltaLongitude / stepsLongitude;

      var latitudeIndex = Math.floor((latitude - minimumLatitude) / stepSizeLatitude);
      var longitudeIndex = Math.floor((longitude - minimumLongitude) / stepSizeLongitude);

      if (latitudeIndex < 0) latitudeIndex = 0;
      if (longitudeIndex < 0) longitudeIndex = 0;
      try{
        var heatmapValue = heatmapObject.counts_ints2D[heatmapObject.counts_ints2D.length - latitudeIndex - 1][longitudeIndex];
        return heatmapValue;
      }
        catch (err)
      {
        return heatmap.counts_ints2D[0][0];
      }
  },

  processEvent: function(event){
      var map = this.bbox_widget.viewer.mapPanel.map;
      var pixel = event.xy;
      var mercator = map.getLonLatFromViewPortPx(pixel);
      var epsg4326 = new OpenLayers.Projection("EPSG:4326");
      var epsg900913 = new OpenLayers.Projection("EPSG:900913");
      var point = mercator.transform(epsg900913, epsg4326);
      var count = this.getCountGeodetic(this.heatmapObject, point.lat, point.lon) + this.global_layers;
      if (count < 0) count = 0;
      var message = count + " layers";
      this.tooltip.initTarget('ge_searchWindow');
      this.tooltip.show();
      this.tooltip.body.dom.innerHTML = message;

  }

});
