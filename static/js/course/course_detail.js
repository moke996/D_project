$(function () {
  let $course_data = $(".course-data");
  let sVideoUrl = $course_data.data('video-url');
  let sCoverUrl = $course_data.data('cover-url');

  let player = cyberplayer("course-video").setup({
    width: '100%',
    height: 650,
    file: sVideoUrl,
    image: sCoverUrl,
    autostart: false,            // 自动播放
    stretching: "uniform",
    repeat: false,               // 重复播放
    volume: 100,                 // 音量
    controls: true,              // 播放进度条
    ak: '51370a44b07e4f54b9c5be2154b028f3'
  });

});