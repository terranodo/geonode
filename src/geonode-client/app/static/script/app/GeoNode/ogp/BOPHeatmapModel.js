Ext.namespace("GeoNode");

GeoNode.BOPHeatmapModel = Ext.extend(Ext.util.Observable, {

    radiusAdjust: 1.1,

    gradientStops: {
        0.00: 0xffffff00,
        0.10: 0x99e9fdff,
        0.20: 0x00c9fcff,
        0.30: 0x00e9fdff,
        0.30: 0x00a5fcff,
        0.40: 0x0078f2ff,
        0.50: 0x0e53e9ff,
        0.70: 0x890bbfff,
        0.80: 0x99019aff,
        0.90: 0x990664ff,
        0.99: 0x660000ff,
        1.00: 0x000000ff
    },

    constructor: function(config) {
      var self = this;
      Ext.apply(this, config);

      if (config && config.params && config.params["q.text"] && config.respHeatmap) {
          this.map = GeoExt.MapPanel.guess().map;
          this.drawHeatmapOpenLayers(config.params["q.text"], config.respHeatmap);
      }

      Ext.QuickTips.init();

      this.tooltip = new Ext.ToolTip({
          html: 'test',
          cls: 'ogp-tooltip',
          hideDelay: 0,
          showDelay: 0,
          width: 80
        });

    },

    setQueryParameters: function(){

        var extent = this.createExtent(this.params["q.geo"]);
        var center = extent.getCenterLonLat();

        // if (extent){
        //   //extent = extent.transform(new OpenLayers.Projection('EPSG:900913'), new OpenLayers.Projection('EPSG:4326'));
        //   var bbox = {
        //     minX: extent.left,
        //     maxX: extent.right,
        //     minY: extent.bottom,
        //     maxY: extent.top
        //   };
        //   GeoNode.solr.center = {
        //     centerX: center.lat,
        //     centerY: center.lon
        //   }
        //   var params = GeoNode.solr.getOgpSpatialQueryParams(bbox);
        //   GeoNode.queryTerms.intx = params.intx;
        //   GeoNode.queryTerms.bf = params.bf;
        //   heatmapParams['facet.heatmap.geom'] = params['facet.heatmap.geom'];
        // }
    },


    /**
     * Converts the provided bounding box parameter from string to `OpenLayers.Bounds`
     * object (e.g. "[-90,-180 TO 90,180]" -> [-90,-180,90,180])
     * @param {String} requested bbox as string
     * @return {OpenLayers.Bounds}
     */
    createExtent: function(bboxString){
        var bounds;
        bounds = (bboxString.replace(/[^\d .,-]/g, '').replace(/\s+/g, ',')).split(',');

        return new OpenLayers.Bounds(
            parseFloat(bounds[0]),
            parseFloat(bounds[1]),
            parseFloat(bounds[2]),
            parseFloat(bounds[3])
        );
    },

    /**
     * Creates a new `Heatmap.Layer` instance with responsed heatmap from API
     * @param {String} heatMapLayerName layer name in layertree (equal to keyword)
     * @param {Object} respHeatmap heatmap parameters as JSON response from API
     */
    drawHeatmapOpenLayers: function(heatMapLayerName, respHeatmap){

        // don't do anything, if heatmap parameters are empty
        var heatmap = respHeatmap["a.hm"];
        if (heatmap == null){
            return;
        };

        this.heatmapLayer = new Heatmap.Layer(heatMapLayerName);

        // set additional abstract property to be used as tooltip on
        // mouseover event on layer record in layertree
        this.heatmapLayer["abstract"] = heatMapLayerName;

        this.heatmapLayer.points = [];

        var counts_ints2D = heatmap.counts_ints2D;
        var gridLevel = heatmap.gridLevel;
        var gridRows = heatmap.rows;
        var gridColumns = heatmap.columns;
        var minMaxValue = this.heatmapMinMax(counts_ints2D, gridRows, gridColumns);
        var maxValue = minMaxValue[1];
        if (maxValue == -1) {
            return;
        }
        var minX = heatmap.minX;
        var maxX = heatmap.maxX;
        var dx = maxX - minX;
        var minY = heatmap.minY;
        var maxY = heatmap.maxY;
        var dy = maxY - minY;

        var sx = dx / gridColumns;
        var sy = dy / gridRows;

        this.heatmapLayer.setGradientStops(this.gradientStops);

        for (var i = 0 ; i < gridRows ; i++){
            for (var j = 0 ; j < gridColumns ; j++){
              try{
                var hmVal = counts_ints2D[counts_ints2D.length - i - 1][j];
                if (hmVal && hmVal !== null){
                    var lat = minY + i*sy + (0.5 * sy);
                    var lon = minX + j*sx + (0.5 * sx);
                    var radius = this.computeRadius(lat, lon, sx, sy);
                    var mercator = this.WGS84ToMercator(lon, lat);
                    var scaledValue = this.rescaleHeatmapValue(hmVal, minMaxValue);
                    var radiusFactor = this.getRadiusFactor();
                    this.heatmapLayer.addSource(new Heatmap.Source(mercator, radius*radiusFactor*this.radiusAdjust, scaledValue));
                }
              }
              catch (error){
                console.log("error making heatmap: " + error);
              }
            }
        }
        this.heatmapLayer.setOpacity(0.50);

        if(this.map.getLayersByName(heatMapLayerName).length == 0 && this.heatmapLayer.points.length > 0){

            this.layertree = app.layerTree;
            var folderName = "BOP Heatmap Layers";

            // TODO: this is WIP state --> source don't be created correct yet
            // so the heatmap layer cannot be persisted
            // var sourceConfig = {
            //     "config":{
            //         "ptype":"gxp_olsource"
            //     },
            //     "type": "Heatmap.Layer",
            //     "source": 5,
            //     "name": this.heatmapLayer.name,
            //     "visibility": true,
            //     "fixed": true,
            //     "group": folderName
            // };
            //var source = app.addLayerSource(sourceConfig);
            //var heatmapRecord = source.createLayerRecord(sourceConfig);
            //app.mapPanel.layers.add([heatmapRecord]);

            this.map.addLayer(this.heatmapLayer);
            this.map.raiseLayer(this.heatmapLayer, this.map.layers.length);
            this.layertree.addCategoryFolder({group: folderName}, true);
            this.createLayerTreeNode(folderName, this.heatmapLayer);
        } else {
            this.heatmapLayer.redraw();
        }
    },

    createLayerTreeNode: function(folderName, layer){
        var ltPanel = Ext.getCmp('treecontent');
        var rootNode = this.layertree.tree.getRootNode();
        var parentNode;
        rootNode.cascade(function(node){
            if (node.text === folderName){
                parentNode = node;
            }
        });
        if (parentNode){
            parentNode.appendChild({
                plugins: [{ptype: 'gx_layer'}],
                layer: layer,
                text: layer.name,
                layerStore: this.layertree.target.mapPanel.layers,
                leaf: true
            });
        }
    },

    getNextAvaliableZIndex: function(){
        var zIdx = 0;
        Ext.each(this.map.layers, function(l){
            if (l.getZIndex() > zIdx) {
              zIdx = l.getZIndex();
            }
        })
        return zIdx;
    },

    getRadiusFactor: function(){
        var factor = [1.6, 1.5, 2.6, 2.4, 2.2, 1.8, 2., 2., 2.];
        var zoomLevel = this.map.getZoom();
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

    heatmapMinMax: function (heatmap, sLat, sLon){
      var max = -1;
      var min = Number.MAX_VALUE;
      for (var i = 0 ; i < sLat ; i++){
        var currentRow = heatmap[i];
        if (currentRow == null){
            heatmap[i] = currentRow = []
        }
        for (var j = 0 ; j < sLon ; j++){
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

    rescaleHeatmapValue: function(value, minMaxValue){
        if (value == null){
          return 0;
        };

        if (value == -1){
          return -1;
        };

        if (value == 0){
          return 0;
        };

        if ((minMaxValue[1] - minMaxValue[0]) === 0){
            return 0;
        }
        return (value - minMaxValue[0]) / (minMaxValue[1] - minMaxValue[0]);
    },

    computeRadius: function(latitude, longitude, latitudeStepSize, longitudeStepSize){
      var mercator1 = this.WGS84ToMercator(longitude, latitude);
      var pixel1 = this.map.getPixelFromLonLat(mercator1);
      var mercator2 = this.WGS84ToMercator(longitude + longitudeStepSize, latitude + latitudeStepSize);
      var pixel2 = this.map.getPixelFromLonLat(mercator2);
      var deltaLatitude = Math.abs(pixel1.x - pixel2.x);
      var deltaLongitude = Math.abs(pixel1.y - pixel2.y);
      var delta = Math.max(deltaLatitude, deltaLongitude);
      return Math.ceil(delta / 2.);
    },

    WGS84ToMercator: function(the_lon, the_lat) {
        // returns -infinity for -90.0 lat; a bug?
        var lat = parseFloat(the_lat);
        var lon = parseFloat(the_lon);
        if (lat >= 90) {
          lat = 89.99;
        }
        if (lat <= -90) {
          lat = -89.99;
        }
        if (lon >= 180) {
          lon = 179.99;
        }
        if (lon <= -180) {
          lon = -179.99;
        }
        return OpenLayers.Layer.SphericalMercator.forwardMercator(lon, lat);
    }
});
